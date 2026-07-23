output "api_load_balancer_dns_name" {
  value = aws_lb.api.dns_name
}

output "image_bucket_name" {
  value = aws_s3_bucket.images.id
}

output "postgres_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true
}

output "valkey_primary_endpoint" {
  value     = aws_elasticache_replication_group.valkey.primary_endpoint_address
  sensitive = true
}

output "api_ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "worker_ecr_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}
