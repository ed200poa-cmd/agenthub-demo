# Kubernetes Failure Reproduction Log

Four failure modes reproduced against this repository's Deployment on a
local k3s cluster (k3d on Colima), recording what each one looks like in
`kubectl` output.

## Environment

```
k3s        v1.35.5+k3s1  (k3d v5.9.0)
Docker     29.5.2 (Colima 0.10.3)
kubectl    v1.36.3
image      agenthub:local, built from the repository Dockerfile
```

## Baseline

```
$ kubectl apply -f deploy/k8s/deployment.yaml -f deploy/k8s/service.yaml
deployment.apps/agenthub created
service/agenthub created

$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
agenthub-76f5c4d9bd-4m7rj   1/1     Running   0          9s

$ kubectl port-forward svc/agenthub 8080:80
$ curl http://localhost:8080/health
{"status":"ok","mode":"demo","anthropic_key_set":true,"supabase_connected":false}
HTTP 200
```

## Failure and symptom table

| Trigger | `kubectl get pods` | Where the real cause shows up | Cause | Fix |
|---|---|---|---|---|
| Memory limit set to 10Mi | `CrashLoopBackOff` | `describe pod` → `Last State: Terminated, Reason: OOMKilled, Exit Code: 137` | Container exceeded its memory limit and was killed by the kernel | Raise the limit or reduce application memory use |
| `envFrom` secret name misspelled | `CreateContainerConfigError` | `get events` → `Error: secret "agenthub-secretz" not found` | Referenced Secret does not exist, so the kubelet cannot build the container config | Correct the name, confirm with `kubectl get secrets` |
| Readiness probe path `/healthz` | `Running` but `0/1` | `get events` → `Readiness probe failed: HTTP probe failed with statuscode: 404` | Probe path does not match an application route | Point the probe at a route the app actually serves |
| Image tag that does not exist | `ErrImageNeverPull` or `ImagePullBackOff` | `get events` → `Container image ... is not present with pull policy of Never` / `Error: ImagePullBackOff` | Tag is absent from the node, and the pull policy decides which of the two errors appears | Restore the correct tag, or rebuild and import the image |

---

## 1. OOMKilled

`kubectl set resources --limits=memory=10Mi` alone is rejected, because the
manifest requests 128Mi:

```
error: failed to patch resources update to pod template Deployment.apps "agenthub" is invalid:
spec.template.spec.containers[0].resources.requests: Invalid value: "128Mi":
must be less than or equal to memory limit of 10Mi
```

Lowering both:

```
$ kubectl set resources deployment/agenthub --requests=memory=10Mi --limits=memory=10Mi
deployment.apps/agenthub resource requirements updated

$ kubectl get pods
NAME                        READY   STATUS             RESTARTS      AGE
agenthub-65957b648b-52zzv   0/1     CrashLoopBackOff   2 (16s ago)   29s

$ kubectl describe pod -l app=agenthub
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
    Restart Count:  2
```

The surface status is `CrashLoopBackOff`. `OOMKilled` and exit code 137
appear only under `Last State` in `describe pod`, so the restart-loop
status alone does not identify the cause.

## 2. Missing Secret

`kubectl set env --from=secret/...` validates the Secret client-side and
never reaches the cluster:

```
$ kubectl set env deployment/agenthub --from=secret/agenthub-secretz
Error from server (NotFound): secrets "agenthub-secretz" not found
```

Patching the `envFrom` reference directly does reproduce it:

```
$ kubectl patch deployment agenthub --type=json \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/envFrom/0/secretRef/name","value":"agenthub-secretz"}]'
deployment.apps/agenthub patched

$ kubectl get pods
NAME                       READY   STATUS                       RESTARTS   AGE
agenthub-f4bdbb645-h4ftr   0/1     CreateContainerConfigError   0          20s

$ kubectl get events --sort-by=.lastTimestamp
Warning   Failed   pod/agenthub-f4bdbb645-h4ftr   Error: secret "agenthub-secretz" not found
```

A missing Secret referenced through `envFrom` produces
`CreateContainerConfigError`, not `CrashLoopBackOff`. The container never
starts, so there is nothing to crash-loop.

## 3. Readiness probe path mismatch

```
$ kubectl patch deployment agenthub --type=json \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/healthz"}]'
deployment.apps/agenthub patched

$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
agenthub-7bf9b9d9ff-kkf2r   0/1     Running   0          35s

$ kubectl get events --sort-by=.lastTimestamp
Warning   Unhealthy   pod/agenthub-7bf9b9d9ff-kkf2r   Readiness probe failed: HTTP probe failed with statuscode: 404

$ kubectl get endpoints agenthub
NAME       ENDPOINTS        AGE
agenthub   10.42.0.9:8000   3m40s
```

`STATUS` stays `Running` and `RESTARTS` stays 0, so the pod looks healthy
in a quick listing. `READY 0/1` is the signal. The Service endpoint list
contains only the previous pod's IP, which is how this reaches users:
traffic never routes to the new pod.

## 4. Image tag that does not exist

With this manifest's `imagePullPolicy: Never`:

```
$ kubectl set image deployment/agenthub agenthub=agenthub:doesnotexist
deployment.apps/agenthub image updated

$ kubectl get pods
NAME                        READY   STATUS              RESTARTS   AGE
agenthub-5f8cd889c8-zzcg8   0/1     ErrImageNeverPull   0          25s

$ kubectl get events --sort-by=.lastTimestamp
Warning   ErrImageNeverPull   Container image "agenthub:doesnotexist" is not present with pull policy of Never
```

Switching the pull policy so the kubelet actually contacts a registry
produces `ImagePullBackOff` instead:

```
$ kubectl patch deployment agenthub --type=json \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"ghcr.io/ed200poa-cmd/agenthub:doesnotexist"},
         {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
deployment.apps/agenthub patched

$ kubectl get events --sort-by=.lastTimestamp
Normal    Pulling   Pulling image "ghcr.io/ed200poa-cmd/agenthub:doesnotexist"
Warning   Failed    Failed to pull image "ghcr.io/ed200poa-cmd/agenthub:doesnotexist": failed to resolve reference: failed to authorize: failed to fetch anonymous token: unexpected status from GET request to https://ghcr.io/token?...: 403 Forbidden
Normal    BackOff   Back-off pulling image "ghcr.io/ed200poa-cmd/agenthub:doesnotexist"
Warning   Failed    Error: ImagePullBackOff
```

The two statuses distinguish the cause. `ErrImageNeverPull` means the
image is absent from the node and the policy forbids fetching it.
`ImagePullBackOff` means a pull was attempted and failed. The 403 from
ghcr.io also shows that a private or nonexistent repository returns an
authorization failure rather than a not-found.

## Restore

Each failure was reverted by reapplying the manifest:

```
$ kubectl apply -f deploy/k8s/deployment.yaml
$ kubectl rollout status deployment/agenthub
deployment "agenthub" successfully rolled out

$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
agenthub-76f5c4d9bd-4m7rj   1/1     Running   0          5m21s
```
