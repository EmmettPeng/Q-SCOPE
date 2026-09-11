import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from qscn.analysis import (
    apply_hit_rule,
    parse_domtblout,
    parse_ga_thresholds,
    parse_prodigal_gff,
    parse_prodigal_protein_headers,
    run_hmmscan,
    run_prodigal,
)
from qscn.schemas import InputKind


class _Completed:
    returncode = 0
    stderr = ""
    wall_seconds = 0.1
    peak_rss_kb = 10


class AnalysisAdapterTest(unittest.TestCase):
    @patch("qscn.analysis.run_external", return_value=_Completed())
    def test_genome_prodigal_mode_is_explicit(self, mocked):
        with tempfile.TemporaryDirectory() as temp:
            sample = {"sample_id": "s", "display_name": "S", "fasta_path": "/input.fna"}
            output = Path(temp)
            (output / "s.gff").write_text(
                "##gff-version 3\ncontig\tProdigal\tCDS\t1\t90\t.\t+\t0\tID=gene_1;partial=10\n",
                encoding="utf-8",
            )
            (output / "s.faa").write_text(
                ">contig_1 # 1 # 90 # 1 # ID=gene_1;partial=10\nMAAA\n",
                encoding="utf-8",
            )
            run_prodigal(sample, InputKind.genome, output)
            self.assertEqual(mocked.call_args.args[0][-2:], ["single", "-q"])
            with self.assertRaisesRegex(Exception, "only used for genome"):
                run_prodigal(sample, InputKind.protein, Path(temp))

    @patch("qscn.analysis.run_external", return_value=_Completed())
    def test_dotted_sample_ids_produce_distinct_prodigal_outputs(self, _mocked):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            sample_ids = ["AS-MESO-3CA.107", "AS-MESO-3CA.288"]
            for sample_id in sample_ids:
                (output / f"{sample_id}.gff").write_text(
                    "##gff-version 3\ncontig\tProdigal\tCDS\t1\t90\t.\t+\t0\t"
                    "ID=gene_1;partial=00\n",
                    encoding="utf-8",
                )
                (output / f"{sample_id}.faa").write_text(
                    ">contig_1 # 1 # 90 # 1 # ID=gene_1;partial=00\nMAAA\n",
                    encoding="utf-8",
                )
            outputs = [
                run_prodigal(
                    {"sample_id": sample_id, "display_name": sample_id, "fasta_path": f"/{sample_id}.fa"},
                    InputKind.genome,
                    output,
                )
                for sample_id in sample_ids
            ]
        self.assertEqual(
            [Path(item["protein_path"]).name for item in outputs],
            ["AS-MESO-3CA.107.faa", "AS-MESO-3CA.288.faa"],
        )
        self.assertEqual(
            [Path(item["genes_path"]).name for item in outputs],
            ["AS-MESO-3CA.107.predicted_genes.json", "AS-MESO-3CA.288.predicted_genes.json"],
        )

    def test_prodigal_fasta_ids_map_to_gff_coordinates_and_partial_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gff = root / "sample.gff"
            faa = root / "sample.faa"
            gff.write_text(
                "##gff-version 3\n"
                "NODE_4_length_100\tProdigal\tCDS\t573\t2525\t.\t+\t0\t"
                "ID=1_1;partial=10\n",
                encoding="utf-8",
            )
            faa.write_text(
                ">NODE_4_length_100_1 # 573 # 2525 # 1 # ID=1_1;partial=10\nMAAA\n",
                encoding="utf-8",
            )
            genes = parse_prodigal_protein_headers(faa, gff, "sample")
        self.assertEqual(genes[0]["gene_id"], "NODE_4_length_100_1")
        self.assertEqual(genes[0]["prodigal_internal_id"], "1_1")
        self.assertEqual(genes[0]["contig_id"], "NODE_4_length_100")
        self.assertEqual((genes[0]["start"], genes[0]["end"], genes[0]["strand"]), (573, 2525, "+"))
        self.assertTrue(genes[0]["partial_5prime"])
        self.assertFalse(genes[0]["partial_3prime"])

    def test_domtblout_coordinates_and_coverages(self):
        line = "Profile - 100 Protein - 200 1e-20 80.0 0.0 1 1 1e-22 1e-22 75.0 0.0 2 91 10 109 8 111 0.98 description\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "hits.domtblout"
            path.write_text(line)
            hits = parse_domtblout(path, "sample")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["profile_id"], "Profile")
        self.assertAlmostEqual(hits[0]["hmm_coverage"], 0.9)
        self.assertAlmostEqual(hits[0]["sequence_coverage"], 0.5)
        self.assertEqual(hits[0]["domain_c_evalue"], 1e-22)
        self.assertEqual(hits[0]["domain_i_evalue"], 1e-22)

    def test_ga_thresholds_preserve_sequence_and_domain_scores(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profiles.hmm"
            path.write_text(
                "HMMER3/f\nNAME A\nGA 25 30;\n//\nNAME B\nGA 40;\n//\n",
                encoding="utf-8",
            )
            thresholds = parse_ga_thresholds(path)
        self.assertEqual(thresholds["A"], {"full_score_min": 25, "domain_score_min": 30})
        self.assertEqual(thresholds["B"], {"full_score_min": 40, "domain_score_min": 40})

    def test_evalue_rule_uses_full_and_independent_domain_evalue_only(self):
        hits = [
            {"profile_id": "A", "full_evalue": 1e-8, "domain_i_evalue": 1e-7, "domain_c_evalue": 99, "full_score": -1, "domain_score": -2},
            {"profile_id": "A", "full_evalue": 1e-8, "domain_i_evalue": 1e-3, "domain_c_evalue": 1e-30, "full_score": 500, "domain_score": 500},
        ]
        apply_hit_rule(
            hits,
            "evalue",
            {"full_evalue_max": 1e-5, "domain_i_evalue_max": 1e-5},
        )
        self.assertTrue(hits[0]["pass"])
        self.assertEqual(hits[0]["failure_reasons"], [])
        self.assertFalse(hits[1]["pass"])
        self.assertEqual(hits[1]["failure_reasons"], ["domain_i_evalue"])
        self.assertEqual(hits[0]["hit_rule_version"], "1.0")

    @patch("qscn.analysis.parse_domtblout", return_value=[])
    @patch("qscn.analysis.run_external", return_value=_Completed())
    def test_evalue_scan_uses_full_reporting_and_wide_domain_reporting(self, mocked_run, _):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hmm = root / "db.hmm"
            protein = root / "input.faa"
            hmm.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            protein.write_text(">p\nMAAA\n", encoding="utf-8")
            _, metadata = run_hmmscan(
                "s", protein, hmm, root / "out", "evalue",
                {"full_evalue_max": 1e-5, "domain_i_evalue_max": 1e-6},
            )
        command = mocked_run.call_args.args[0]
        self.assertEqual(command[command.index("-E") + 1], "1e-05")
        self.assertEqual(command[command.index("--domE") + 1], "10")
        self.assertIn("domain_i_evalue<=1e-06", metadata["threshold_rule"])

    def test_prodigal_gff_preserves_contig_coordinates_strand_and_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "genes.gff"
            path.write_text(
                "##gff-version 3\n"
                "left\tProdigal\tCDS\t1\t300\t.\t+\t0\tID=left_1;partial=10\n"
                "right\tProdigal\tCDS\t20\t410\t.\t-\t0\tID=right_1;partial=01\n",
                encoding="utf-8",
            )
            genes = parse_prodigal_gff(path, "sample")
        self.assertEqual(genes[0]["contig_id"], "left")
        self.assertEqual((genes[0]["start"], genes[0]["end"], genes[0]["strand"]), (1, 300, "+"))
        self.assertTrue(genes[0]["partial_5prime"])
        self.assertTrue(genes[1]["partial_3prime"])
        self.assertEqual(genes[1]["strand"], "-")

    @unittest.skipUnless(shutil.which("prodigal"), "Prodigal is available in the release image")
    def test_real_prodigal_on_project_owned_synthetic_genome(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            genome = root / "synthetic.fna"
            codons = ["GCT", "GAA", "CCA", "TTT", "AAG", "GGT"]
            orfs = []
            for index in range(36):
                body = "".join(codons[(index + offset) % len(codons)] for offset in range(280))
                orfs.append("ATG" + body + "TAA" + "C" * 45)
            genome.write_text(">synthetic_contig\n" + "".join(orfs) + "\n", encoding="utf-8")
            sample = {"sample_id": "synthetic", "display_name": "Synthetic", "fasta_path": str(genome)}
            outputs = run_prodigal(sample, InputKind.genome, root / "predictions")
            genes = __import__("json").loads(Path(outputs["genes_path"]).read_text(encoding="utf-8"))
        self.assertGreater(len(genes), 0)
        self.assertTrue(all(item["contig_id"] == "synthetic_contig" for item in genes))
        self.assertTrue(all(item["strand"] in {"+", "-"} for item in genes))
        self.assertTrue(Path(outputs["genes_tsv_path"]).name.endswith("predicted_genes.tsv"))

    @unittest.skipUnless(
        shutil.which("hmmbuild") and shutil.which("hmmscan"),
        "HMMER is available in the release image",
    )
    def test_real_miniature_hmmer_workflow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            alignment = root / "sender.sto"
            alignment.write_text(
                "# STOCKHOLM 1.0\nseq1 MPEPTIDEWLFQH\nseq2 MPEPTIDEWLFQY\n//\n",
                encoding="utf-8",
            )
            hmm = root / "profiles.hmm"
            subprocess.run(["hmmbuild", "-n", "SyntheticSender", str(hmm), str(alignment)], check=True, capture_output=True)
            subprocess.run(["hmmpress", str(hmm)], check=True, capture_output=True)
            protein = root / "sample.faa"
            protein.write_text(">protein_1\nMPEPTIDEWLFQH\n", encoding="utf-8")
            hits, metadata = run_hmmscan(
                "sample", protein, hmm, root / "scan", "evalue",
                {"full_evalue_max": 10.0, "domain_i_evalue_max": 10.0},
            )
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["profile_id"], "SyntheticSender")
        self.assertTrue(hits[0]["pass"])
        self.assertGreater(metadata["wall_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
