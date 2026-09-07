# One image, three commands, both modes.
#
#   web      gunicorn, the board and the settings UI      (the default below)
#   worker   generate.py --tick, on a loop                (docker-compose.yml)
#   migrate  migrate.py, App Platform's pre-deploy job    (cloud only)
#
# That is decision 2's "one artefact" argument arriving somewhere it pays: the
# hosted version does not run the same *file* a self-hoster runs, but it runs
# the same image. App Platform builds this; docker-compose.yml runs it locally
# and is the Phase 7 self-host deliverable.

# Debian slim, and deliberately not Alpine. strftime("%-d") — which every date
# on the board goes through — is a glibc extension. musl does not have it, and
# the failure would be silently wrong dates rather than a build error.
FROM python:3.11-slim

# Bytecode files in a layer help nobody, and unbuffered output means a crash
# loop shows its traceback instead of an empty log.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies before source, so editing a template does not reinstall the
# world. requirements-cloud.txt pulls in requirements.txt, so this is both.
#
# Yes, that puts psycopg in the image a self-hoster runs. One image is the whole
# point, and 5 MB of driver is a fair price for it — the constraint CLAUDE.md
# actually protects is the *Pi*, which installs requirements.txt through
# deploy_to_pi.sh and never sees this file. requirements-dev.txt is absent on
# purpose: the site generator and Pillow have no business on a server.
COPY requirements.txt requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Gunicorn is not a runtime dependency of the app — nothing imports it — so it
# is installed here rather than in requirements.txt, where it would follow
# deploy_to_pi.sh onto a Pi that serves with the Flask dev server.
RUN pip install --no-cache-dir "gunicorn==23.0.0"

COPY dinkydash/ ./dinkydash/
COPY web/ ./web/
COPY migrations/ ./migrations/
COPY app.py generate.py migrate.py sample_board.py config.example.yaml ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Not root. The app writes only to the config directory, which is a bind mount
# in single mode and nothing at all in cloud mode, so it needs no more than this.
RUN useradd --create-home --uid 10001 dinkydash \
    && chown -R dinkydash:dinkydash /app
USER dinkydash

EXPOSE 5000

# Seeds an empty mounted directory with config.example.yaml, then execs whatever
# it was given — so `docker run … python migrate.py` still means that.
ENTRYPOINT ["docker-entrypoint.sh"]

# The web role, because it is the one an image with no command should serve.
# The other two override it and are one word each:
#
#   docker run … python generate.py --tick
#   docker run … python migrate.py
#
# --workers 2 because App Platform's smallest instance is 1 vCPU / 512 MiB and
# the app is I/O-light; --threads because it waits on calendars and on Claude.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--threads", "4", "--worker-class", "gthread", \
     "--timeout", "60", "--access-logfile", "-", "app:app"]
