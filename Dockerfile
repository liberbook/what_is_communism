FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    cm-super \
    pandoc \
    poppler-utils \
    python3 \
    texlive-fonts-recommended \
    texlive-lang-cyrillic \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-latex-recommended \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY . /work
RUN chmod +x /work/build.sh /work/build_book.py /work/compare_outputs.py /work/docker_build.sh \
 && mkdir -p /work/out \
 && chmod -R a+rwX /work/russian /work/ukrainian /work/italiano /work/out
CMD ["/work/build.sh"]
