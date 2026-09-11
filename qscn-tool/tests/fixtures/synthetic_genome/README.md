# Project-owned synthetic genome fixture

`tests/test_analysis.py::test_real_prodigal_on_project_owned_synthetic_genome`
deterministically generates a 32 kb artificial contig from repeated synthetic
open reading frames. No biological sequence or third-party database content is
used. The fixture is covered by the repository Apache-2.0 license.

The real Prodigal test verifies generated FAA/CDS/GFF and the structured gene
mapping. `expected_partial.gff` separately fixes the parser contract for plus
and minus strands and both partial flags, because Prodigal gene calls can vary
between tool versions.
