# super-search-backend

Update Hi

Instructions to deploy image on to ECR -

1. podman machine init
2. podman machine start
3. /**_ make sure to have creds updated _**/
4. aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 163678476612.dkr.ecr.us-east-1.amazonaws.com
5. docker build -t supersearch/backend . --platform linux/amd64
6. docker tag supersearch/backend:latest 163678476612.dkr.ecr.us-east-1.amazonaws.com/supersearch/backend:latest
7. docker push 163678476612.dkr.ecr.us-east-1.amazonaws.com/supersearch/backend:latest

once above commands are successful, Go to ECR and check if you can find latest image deployed.

then Go to EKS and check clusters. You will need to restart cluster for it to point to latest image.
Amazon Elastic Kubernetes Service > Clusters > super-search-cluster > deployment-2048 > copy latest image id and execute below command in terminal
kubectl rollout restart deployment deployment-2048 -n game-2048

to checkout logs, use below command - kubectl logs deployment-2048-6b5dd57498-45qh2 -n game-2048