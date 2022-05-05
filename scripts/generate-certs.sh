#!/bin/bash
set -eu

function generate_v3_file() {
  local v3_file=$1
  local fqdn=$2
  cat <<EOF >"${v3_file}"
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = ${fqdn}
DNS.2 = *.${fqdn}
EOF
}

function generate_openssl_cnf_file() {
  folder_path="$1"
  #shellcheck disable=SC2016
  echo '
[ ca ]
default_ca = CA_default
[ CA_default ]
dir            = '"${folder_path}"'           # Where everything is kept
certs          = $dir/certs               # Where the issued certs are kept
crl_dir        = $dir/crl                 # Where the issued crl are kept
database       = $dir/index.txt           # database index file.
new_certs_dir  = $dir/certs               # default place for new certs.
certificate    = $dir/ca.crt        # The CA certificate
serial         = $dir/serial              # The current serial number
crl            = $dir/crl.pem             # The current CRL
private_key    = $dir/private/ca.key      # The private key
RANDFILE       = $dir/.rnd                # private random number file
nameopt        = default_ca
certopt        = default_ca
policy         = policy_match
default_days   = 365
default_md     = sha256

[ policy_match ]
countryName            = optional
stateOrProvinceName    = optional
organizationName       = optional
organizationalUnitName = optional
commonName             = supplied
emailAddress           = optional

[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_req]
basicConstraints = CA:TRUE
' >"${folder_path}/openssl.cnf"
}

function create_certs_related_folder_and_files() {
  local folder="$1"
  mkdir -p "${folder}"
  echo 1000 >"${folder}/serial"
  touch "${folder}/index.txt"
  generate_openssl_cnf_file "${folder}"
}

function create_certificates() {
  local fqdn="${1}"
  local root_ca_cert_file="$2"
  local tls_cert_file="$3"
  local tls_key_file="$4"
  local identity_pfx_file="${5}"
  local root_ca_password="${6}"
  local self_signed_cert_validity="${7}"
  local root_ca_subj="/C=US/ST=NY/O=UiPath, Inc./CN=UiPath AS Root CA"
  local tls_cert_subj="/C=US/ST=NY/O=UiPath, Inc./CN=UiPath Automation Suite"
  local key_length=2048
  local certs_folder_path

  certs_folder_path="$(dirname "${root_ca_cert_file}")"
  [[ -d ${certs_folder_path} ]] || mkdir -p "${certs_folder_path}"

  echo "Using ${certs_folder_path} to store certificates"
  local v3_file="${certs_folder_path}/v3.txt"

  # Generate root CA
  create_certs_related_folder_and_files "${certs_folder_path}"
  openssl genrsa -des3 -passout pass:"$root_ca_password" -out "${certs_folder_path}/rootCA.crt.key" "${key_length}"
  openssl req -new -x509 -days "${self_signed_cert_validity}" -passin pass:"$root_ca_password" -config "${certs_folder_path}/openssl.cnf" -sha256 -extensions v3_req -key "${certs_folder_path}/rootCA.crt.key" -out "${root_ca_cert_file}" -subj "${root_ca_subj}"

  # Generate server cert
  generate_v3_file "$v3_file" "$fqdn"
  openssl genrsa -out "${tls_key_file}" "${key_length}"
  openssl req -new -key "${tls_key_file}" -out "${certs_folder_path}/server.csr" -subj "${tls_cert_subj}"
  openssl x509 -req -in "${certs_folder_path}/server.csr" -passin pass:"$root_ca_password" -CA "${root_ca_cert_file}" -CAkey "${certs_folder_path}/rootCA.crt.key" -out "${tls_cert_file}" -CAcreateserial -days "${self_signed_cert_validity}" -sha256 -extfile "${v3_file}"

  # Generate identity certificate
  openssl pkcs12 -export -out "${identity_pfx_file}" -inkey "${certs_folder_path}/rootCA.crt.key" -in "${root_ca_cert_file}" --passin pass:"${root_ca_password}" -passout pass:"${root_ca_password}"
  echo "TLS certificate generated"
}

function main() {
  local fqdn
  local root_ca_cert_file
  local tls_cert_file
  local tls_key_file
  local root_ca_password
  local self_signed_cert_validity
  local identity_pfx_file

  fqdn="$(jq -r ".fqdn" <"/root/installer/input.json")"
  root_ca_cert_file="$(jq -r ".server_certificate.ca_cert_file" <"/root/installer/input.json")"
  tls_cert_file="$(jq -r ".server_certificate.tls_cert_file" <"/root/installer/input.json")"
  tls_key_file="$(jq -r ".server_certificate.tls_key_file" <"/root/installer/input.json")"
  root_ca_password="$(jq -r ".identity_certificate.token_signing_cert_pass" <"/root/installer/input.json")"
  identity_pfx_file="$(jq -r ".identity_certificate.token_signing_cert_file" <"/root/installer/input.json")"
  self_signed_cert_validity="$(jq -r ".self_signed_cert_validity" <"/root/installer/input.json")"

  create_certificates "${fqdn}" "${root_ca_cert_file}" "${tls_cert_file}" "${tls_key_file}" "${identity_pfx_file}" "${root_ca_password}" "${self_signed_cert_validity}"
}

main "$@"
