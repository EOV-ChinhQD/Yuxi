---
name: Docker Issue
about: Report a docker startup or container issue
title: '[DOCKER] '
labels: environment, docker
assignees: ''
---

**Describe the Docker issue**
A clear and concise description of what the startup or container issue is.

**Docker Compose Configuration**
Relevant services in docker-compose.yml or environment variables.

**Container Logs**
```bash
docker logs api-dev --tail 100
# or
docker logs web-dev --tail 100
```

**Environment Information**
 - OS: [e.g. Ubuntu 22.04 / macOS / Windows WSL2]
 - Docker Version: [e.g. 24.0.5]
 - Docker Compose Version: [e.g. 2.20.2]

**Additional context**
Add any other context about the problem here.
