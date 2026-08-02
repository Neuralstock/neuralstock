# NeuralStock Blender worker licensing and source notice

The NeuralStock Blender worker is an aggregate container. It is not licensed
solely under MIT. The OCI license expression is:

`MIT AND GPL-2.0-or-later AND LicenseRef-Blender-Third-Party AND LicenseRef-Ubuntu-Runtime-Packages`

This notice is an inventory aid, not a replacement for the license texts in
the image.

## NeuralStock worker code — MIT

Repository-owned Python and shell code is licensed under MIT. The complete MIT
text is installed at:

`/usr/share/neuralstock/licenses/neuralstock-MIT.txt`

## Blender 4.5.12 LTS — GPL and bundled third-party terms

The image contains the unmodified official Blender 4.5.12 Linux x64 binary
archive. The archive and its SHA-256 are:

- <https://download.blender.org/release/Blender4.5/blender-4.5.12-linux-x64.tar.xz>
- `95e3a2dfedba3bd32ca54fc355eac6b15a11986954ccb02815a07535d0120a25`

Blender's archive identifies Blender under GPL-2.0-or-later and includes code
and libraries under additional GPL-compatible licenses. Those exact notices
are retained in the image at:

- `/opt/blender/copyright.txt`
- `/opt/blender/license/license.md`
- `/opt/blender/license/licenses.json`
- `/opt/blender/license/`

`LicenseRef-Blender-Third-Party` means the complete set of component-specific
terms enumerated by that retained Blender license tree.

The matching official source archive is:

- <https://download.blender.org/source/blender-4.5.12.tar.xz>
- `9cb86825c95e4f0a33bfd41eb574426f2f69aa6c310497e289fdb54cc6482f1b`

Anyone publishing the worker image or Docker archive must make the exact
matching source available to recipients in a GPL-compliant way. For a public
release, mirror the verified source archive alongside the image rather than
depending only on the continued availability of the upstream URL.

## Ubuntu runtime packages — package-specific terms

The base and runtime packages come from the dated Ubuntu snapshot recorded in
`/usr/share/neuralstock/container-locks/ubuntu.sources`. Directly requested
package versions are recorded in the adjacent `ubuntu-*.lock` files, while
the image's dpkg database records the complete installed package inventory.

Ubuntu is an aggregate of packages under package-specific licenses.
`LicenseRef-Ubuntu-Runtime-Packages` means those terms. Debian-format copyright
and license notices are retained under `/usr/share/doc/*/copyright` and common
license texts under `/usr/share/common-licenses/`.

The final stage also redistributes the CA certificate bundle copied from the
fetch stage. Its exact package version is pinned in `ubuntu-bootstrap.lock`,
and its notice is retained explicitly at
`/usr/share/doc/ca-certificates/copyright` even though the package itself is
not installed in the final stage.

A publisher must review the installed package inventory, preserve those
notices, and provide corresponding source for packages whose terms require it.
The word "Ubuntu" identifies compatibility and origin only; the image does not
claim Canonical endorsement.

## Public OCI publication gate

Before publishing this image or its Docker archive:

1. Verify the OCI license expression and every in-image notice path above.
2. Retain an SBOM or complete dpkg package/version inventory for the digest.
3. Mirror the verified Blender source archive alongside the binary image.
4. Make required Ubuntu package sources available for that exact inventory.
5. Publish this notice with the image and do not describe the aggregate as
   MIT-only.
