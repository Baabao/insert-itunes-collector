
{{- define "insert-itunes-collector.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "insert-itunes-collector.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "insert-itunes-collector.labels" -}}
helm.sh/chart: {{ include "insert-itunes-collector.chart" . }}
app.kubernetes.io/name: {{ include "insert-itunes-collector.name" . }}
app.kubernetes.io/instance: {{.Release.Name}}
{{- if .Chart.AppVersion}}
app.kubernetes.io/version: {{.Chart.AppVersion | quote}}
{{- end}}
app.kubernetes.io/managed-by: {{.Release.Service}}
{{- end -}}

{{- define "insert-itunes-collector.matchLabels" -}}
app.kubernetes.io/name: {{ include "insert-itunes-collector.name" . }}
app.kubernetes.io/instance: {{.Release.Name}}
{{- end -}}

{{- define "insert-itunes-collector.annotations" -}}
{{- with .Values.annotations}}
{{- toYaml .}}
{{- end}}
cluster: "{{- if eq .Values.global.PROD "production" -}}prod-cluster{{- else if eq .Values.global.PROD "staging" -}}staging-cluster{{- else -}}local-cluster{{- end }}"
environment: "{{- if eq .Values.global.PROD "production" -}}prod{{- else if eq .Values.global.PROD "staging" -}}staging{{- else -}}local{{- end }}"
deploymentTime: {{ now | date "2006-01-02T15:04:05" }}
{{- end -}}

{{/*
AWS
*/}}
{{- define "insert-itunes-collector.aws" -}}
{{- if or (eq .Values.global.PROD "production") (eq .Values.global.PROD "staging") -}}
- name: AWS_ACCESS_KEY_ID
  value: {{ required "You must set a value for AWS_ACCESS_KEY_ID on production/staging in values.yaml" .Values.global.AWS_ACCESS_KEY_ID | quote }}
- name: AWS_SECRET_ACCESS_KEY
  value: {{ required "You must set a value for AWS_SECRET_ACCESS_KEY on production/staging in values.yaml" .Values.global.AWS_SECRET_ACCESS_KEY | quote }}
- name: REGION
  value: {{ required "You must set a value for REGION on production/staging in values.yaml" .Values.global.REGION | quote }}
{{- end -}}
{{- end -}}

{{/*
Database endpoint
*/}}
{{- define "insert-itunes-collector.database" -}}
{{- if or (eq .Values.global.PROD "production") (eq .Values.global.PROD "staging") -}}
- name: POSTGRES_SECRET_ID
  value: {{ required "You must set a value for POSTGRES_SECRET_ID on production/staging in values.yaml" .Values.global.POSTGRES_SECRET_ID | quote }}
{{- end -}}
{{- end -}}

{{/*
Cache endpoint
*/}}
{{- define "insert-itunes-collector.cache" -}}
{{- if or (eq .Values.global.PROD "production") (eq .Values.global.PROD "staging") -}}
- name: CACHE_ENDPOINT
  value: {{ required "You must set a value for CACHE_ENDPOINT on production/staging in values.yaml" .Values.global.CACHE_ENDPOINT | quote }}
{{- end -}}
{{- end -}}