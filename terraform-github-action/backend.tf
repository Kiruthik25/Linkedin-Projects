terraform {
  backend "s3" {
    bucket       = "kiruthik-terrafrom-demo"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = "true"
    encrypt      = true
  }
}