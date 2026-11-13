{{- define "ea.name" -}}experiment-analyzer{{- end -}}

{{- define "ea.labels" -}}
app.kubernetes.io/name: {{ include "ea.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "ea.selector" -}}
app.kubernetes.io/name: {{ include "ea.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "ea.fullname" -}}{{ .Release.Name }}-{{ include "ea.name" . }}{{- end -}}

{{- define "ea.secretName" -}}
{{- if .Values.secrets.create -}}{{ include "ea.fullname" . }}{{- else -}}{{ .Values.secrets.existingSecret }}{{- end -}}
{{- end -}}

{{- define "ea.image" -}}
{{- $tag := required "image.tag is required (the git sha)" .root.Values.image.tag -}}
{{- if .root.Values.image.registry -}}{{ .root.Values.image.registry }}/{{ .name }}:{{ $tag }}{{- else -}}{{ .name }}:{{ $tag }}{{- end -}}
{{- end -}}

{{/* Pod-level hardening shared by the app pods. */}}
{{- define "ea.podSecurity" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .gid }}
fsGroup: {{ .gid }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "ea.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/* Env shared by api, worker and the migrate Job: ConfigMap + secrets, with URLs built from the secret values. */}}
{{- define "ea.appEnv" -}}
{{- $root := .root | default . -}}
{{- $cm := .configMap | default (include "ea.fullname" $root) -}}
{{- with $root -}}
envFrom:
  - configMapRef:
      name: {{ $cm }}
env:
  - name: DJANGO_SECRET_KEY
    valueFrom: { secretKeyRef: { name: {{ include "ea.secretName" . }}, key: DJANGO_SECRET_KEY } }
  - name: POSTGRES_PASSWORD
    valueFrom: { secretKeyRef: { name: {{ include "ea.secretName" . }}, key: POSTGRES_PASSWORD } }
  - name: RABBITMQ_PASSWORD
    valueFrom: { secretKeyRef: { name: {{ include "ea.secretName" . }}, key: RABBITMQ_PASSWORD } }
  - name: DATABASE_URL
    value: "postgres://{{ .Values.postgres.user }}:$(POSTGRES_PASSWORD)@{{ include "ea.fullname" . }}-postgres:5432/{{ .Values.postgres.database }}"
  - name: CELERY_BROKER_URL
    value: "amqp://{{ .Values.rabbitmq.user }}:$(RABBITMQ_PASSWORD)@{{ include "ea.fullname" . }}-rabbitmq:5672//"
  - name: GIT_SHA
    value: {{ .Values.image.tag | quote }}
{{- end -}}
{{- end -}}


{{/* App settings. Rendered into the main ConfigMap and into the migrate hook's own ConfigMap: a pre-upgrade hook
     runs before Helm updates regular resources, so the Job must not read the (old) main ConfigMap. */}}
{{- define "ea.configData" -}}
DJANGO_DEBUG: "false"
# localhost is for the kubelet's HTTP probes, which send Host: localhost.
DJANGO_ALLOWED_HOSTS: {{ printf "%s,localhost" .Values.config.allowedHosts | quote }}
CORS_ALLOWED_ORIGINS: ""
S3_BUCKET: {{ required "config.s3Bucket is required" .Values.config.s3Bucket | quote }}
AWS_REGION: {{ .Values.config.awsRegion | quote }}
{{- if .Values.devS3.enabled }}
S3_ENDPOINT_URL: "http://{{ include "ea.fullname" . }}-moto:5000"
S3_PUBLIC_ENDPOINT_URL: {{ .Values.config.s3PublicEndpointUrl | default (printf "http://%s-moto:5000" (include "ea.fullname" .)) | quote }}
# moto accepts any credentials; these dummy values exist only when devS3 is enabled (local clusters).
AWS_ACCESS_KEY_ID: "testing"
AWS_SECRET_ACCESS_KEY: "testing"
{{- else }}
S3_ENDPOINT_URL: {{ .Values.config.s3EndpointUrl | quote }}
S3_PUBLIC_ENDPOINT_URL: {{ .Values.config.s3PublicEndpointUrl | quote }}
{{- end }}
S3_CREATE_BUCKET: {{ .Values.config.s3CreateBucket | quote }}
# int64: Helm reads 52428800 from values.yaml as a float and would render "5.24288e+07".
UPLOAD_MAX_BYTES: {{ .Values.config.uploadMaxBytes | int64 | quote }}
PRESIGN_EXPIRES_SECONDS: {{ .Values.config.presignExpiresSeconds | int64 | quote }}
DRF_NUM_PROXIES: {{ .Values.config.drfNumProxies | int64 | quote }}
ANALYSIS_RATE: {{ .Values.config.analysisRate | quote }}
LOG_LEVEL: {{ .Values.config.logLevel | quote }}
{{- end -}}
