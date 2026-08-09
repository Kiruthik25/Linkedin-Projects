resource "aws_instance" "ec2_1" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name = "ec2-instance-1"
  }
}

resource "aws_instance" "ec2_2" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name = "ec2-instance-2"
  }
}
