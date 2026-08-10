#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  printf '%s\n' "Usage: $0 VERSION IMAGE_REFERENCE_WITH_DIGEST" >&2
  exit 2
fi

version="$1"
image_reference="$2"
case "$image_reference" in
  *@sha256:*) ;;
  *) printf '%s\n' "Release image must be pinned by sha256 digest." >&2; exit 2 ;;
esac

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir="${QSCN_RELEASE_OUTPUT_DIR:-$repo_root/dist/releases}"
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT INT TERM

make_bundle() {
  platform="$1"
  target="$work_dir/QSCN-v${version}-${platform}"
  mkdir -p "$target/$platform"
  sed "s|__QSCN_IMAGE__|$image_reference|g" "$repo_root/packaging/compose.yml" > "$target/compose.yml"
  cp "$repo_root/packaging/.env.template" "$target/.env.example"
  cp "$repo_root/LICENSE" "$repo_root/THIRD_PARTY_DATA.md" "$repo_root/THIRD_PARTY_SOFTWARE.md" "$target/"
  if [ "$platform" = "macos" ]; then
    cp "$repo_root/packaging/macos/qscn.sh" "$repo_root/packaging/macos/QSCN.command" \
      "$repo_root/packaging/macos/README-macOS.md" "$target/macos/"
    chmod +x "$target/macos/qscn.sh" "$target/macos/QSCN.command"
  elif [ "$platform" = "windows" ]; then
    cp "$repo_root/packaging/windows/qscn.ps1" "$repo_root/packaging/windows/QSCN.cmd" \
      "$repo_root/packaging/windows/README-Windows.md" "$target/windows/"
  else
    cp "$repo_root/packaging/linux/qscn.sh" "$target/linux/QSCN.sh"
    cp "$repo_root/packaging/linux/README-Linux.md" "$target/linux/"
    chmod +x "$target/linux/QSCN.sh"
  fi
  if [ "$platform" = "linux" ]; then
    tar -C "$work_dir" -czf "$output_dir/QSCN-v${version}-linux.tar.gz" "QSCN-v${version}-linux"
  else
    (cd "$work_dir" && zip -q -r "$output_dir/QSCN-v${version}-${platform}.zip" "QSCN-v${version}-${platform}")
  fi
}

mkdir -p "$output_dir"
rm -f "$output_dir/QSCN-v${version}-windows.zip" "$output_dir/QSCN-v${version}-macos.zip" \
  "$output_dir/QSCN-v${version}-linux.tar.gz" "$output_dir/SHA256SUMS"
make_bundle windows
make_bundle macos
make_bundle linux

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$output_dir" && sha256sum "QSCN-v${version}-windows.zip" "QSCN-v${version}-macos.zip" \
    "QSCN-v${version}-linux.tar.gz" > SHA256SUMS)
else
  (cd "$output_dir" && shasum -a 256 "QSCN-v${version}-windows.zip" "QSCN-v${version}-macos.zip" \
    "QSCN-v${version}-linux.tar.gz" > SHA256SUMS)
fi

printf '%s\n' "Release bundles written to $output_dir"
