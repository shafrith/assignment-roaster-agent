# syntax=docker/dockerfile:1

# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

# Vite inlines VITE_* vars at build time.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Render the CSP connect-src origin (scheme://host[:port]) from VITE_API_URL.
# Empty VITE_API_URL = same-origin API; anything that isn't a plain http(s) URL fails the build.
RUN API_ORIGIN="$(printf '%s' "$VITE_API_URL" | sed -nE 's#^(https?://[A-Za-z0-9.-]+(:[0-9]+)?)(/.*)?$#\1#p')" \
    && if [ -n "$VITE_API_URL" ] && [ -z "$API_ORIGIN" ]; then \
         echo "VITE_API_URL must be an http(s) URL, got: $VITE_API_URL" >&2; exit 1; \
       fi \
    && sed "s#__API_ORIGIN__#${API_ORIGIN}#" security-headers.conf > /tmp/security-headers.conf \
    && echo "CSP connect-src API origin: '${API_ORIGIN:-<same-origin>}'"

# ---------- Runtime stage ----------
FROM nginx:alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /tmp/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Fail the image build (not the deploy) if the config doesn't parse.
RUN nginx -t

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
