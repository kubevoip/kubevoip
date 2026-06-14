{{- define "kubevoip.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "kubevoip.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "kubevoip.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- define "kubevoip.serviceAccountName" -}}
{{- default (include "kubevoip.fullname" .) .Values.serviceAccount.name }}
{{- end }}
{{- define "kubevoip.labels" -}}
app.kubernetes.io/name: {{ include "kubevoip.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: kubevoip
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}
