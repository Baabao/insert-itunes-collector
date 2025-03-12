# Insert iTunes collector

## Manually Deploy on Staging

### 1. build image

```shell
docker build -t insert-itunes-collector:latest .
```

### 2. tag image

```shell
docker tag insert-itunes-collector 527466361125.dkr.ecr.ap-northeast-1.amazonaws.com/baabao/insert-itunes-collector:latest
```

### 3. push to ECR (require aws login)

```shell
docker push 527466361125.dkr.ecr.ap-northeast-1.amazonaws.com/baabao/insert-itunes-collector:latest
```

### 4. apply k8s deployment

```shell
kubectl apply -f k8s/staging/deployment.yaml
```

#### Before: ensuring secret.yaml file had already applied

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: insert-itunes-collector-secret
  namespace: baabao-itunes
type: Opaque
data:
  aws_access_key_id: <generate_by_base64>
  aws_secret_access_key: <generate_by_base64>
  aws_region: <generate_by_base64>
  postgres_secret_id: <generate_by_base64>
  cache_endpoint: <generate_by_base64>
```

## How Debug

use debug-pod for debugging

### Apply

```shell
kubectl apply -f k8s/common/debug-pod.yaml
```

### Exec

```shell
kubectl exec -i -t -n baabao-itunes debug-pod -c debug-pod -- sh -c "clear; bash"
```

<br>
<hr>

## Docker

Run it at local environment.

### Build

```shell
docker build -t insert-itunes-collector:latest .
```

### Run

```shell
docker run -d --name=insert-itunes-collector-local insert-itunes-collector 
  -e AWS_ACCESS_KEY_ID= 
  -e AWS_SECRET_ACCESS_KEY= 
  -e PROD= 
  -e REGION=
```

## ECR

Push to AWS ECR

### Login

```shell
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com
```

### Tag

```shell
docker tag insert-itunes-collector <AWS_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com/baabao/insert-itunes-collector:latest
```

### Push

```shell
docker push <AWS_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com/baabao/insert-itunes-collector:latest
```

## EKS

### Show related pod

```shell
kubectl get pod -n baabao-itunes
```

### SSH

```shell
 kubectl exec -i -t -n baabao-itunes insert-itunes-collector-deployment-<RANDOM_ID> -c insert-itunes-collector -- sh -c "clear; bash"
```

## Helm

### Lint

```shell
helm lint helm 
  --set image.repository="<AWS_ACCOUNT_ID>.amazonaws.com/baabao/insert-itunes-collector" 
  --set global.PROD="staging" 
  --set global.AWS_ACCESS_KEY_ID="<AWS_ACCESS_KEY_ID>"
  --set global.AWS_SECRET_ACCESS_KEY="<AWS_SECRET_ACCESS_KEY>" 
  --set global.REGION="<REGION>" 
  --set global.POSTGRES_SECRET_ID="<POSTGRES_SECRET_ID>" 
  --set global.CACHE_ENDPOINT="<CACHE_ENDPOINT>" 
  -n baabao-itunes
```

### Install

```shell
helm install insert-itune-collector helm
  --set image.repository="<AWS_ACCOUNT_ID>.amazonaws.com/baabao/insert-itunes-collector" 
  --set global.PROD="staging" 
  --set global.AWS_ACCESS_KEY_ID="<AWS_ACCESS_KEY_ID>"
  --set global.AWS_SECRET_ACCESS_KEY="<AWS_SECRET_ACCESS_KEY>" 
  --set global.REGION="<REGION>" 
  --set global.POSTGRES_SECRET_ID="<POSTGRES_SECRET_ID>" 
  --set global.CACHE_ENDPOINT="<CACHE_ENDPOINT>" 
  -n baabao-itunes
```

### Uninstall

```shell
helm uninstall insert-itunes-collector -n baabao-itunes
```
