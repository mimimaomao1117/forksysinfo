FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3 tcpdump iproute2 binutils procps bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /project
COPY . /project
CMD ["bash", "scripts/run_all.sh"]
