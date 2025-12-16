import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src_mdcg_pdf_handler to path so we can import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src_mdcg_pdf_handler')))

# Mock the dependency modules BEFORE importing main
# We need to set them in sys.modules so the import in main.py picks up the mocks
ingest_mock = MagicMock()
refine_mock = MagicMock()
convert_mock = MagicMock()
upload_mock = MagicMock()

sys.modules['ingest_manager'] = ingest_mock
sys.modules['refine_manager'] = refine_mock
sys.modules['mdcg_to_json'] = convert_mock
sys.modules['upload_manager'] = upload_mock

# Now import the module under test
import main as orchestrator

class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        # Reset mocks before each test
        ingest_mock.run_batch_processing.reset_mock()
        refine_mock.run_refinement_pipeline.reset_mock()
        convert_mock.convert_md_to_json_structure.reset_mock()
        upload_mock.run_upload_pipeline.reset_mock()

    @patch('sys.argv', ['main.py', '--step', 'ingest'])
    def test_step_ingest(self):
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_called_once()
        refine_mock.run_refinement_pipeline.assert_not_called()
        convert_mock.convert_md_to_json_structure.assert_not_called()
        upload_mock.run_upload_pipeline.assert_not_called()

    @patch('sys.argv', ['main.py', '--step', 'refine'])
    def test_step_refine(self):
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_not_called()
        refine_mock.run_refinement_pipeline.assert_called_once()
        convert_mock.convert_md_to_json_structure.assert_not_called()
        upload_mock.run_upload_pipeline.assert_not_called()

    @patch('sys.argv', ['main.py', '--step', 'convert'])
    def test_step_convert(self):
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_not_called()
        refine_mock.run_refinement_pipeline.assert_not_called()
        convert_mock.convert_md_to_json_structure.assert_called_once()
        upload_mock.run_upload_pipeline.assert_not_called()

    @patch('sys.argv', ['main.py', '--step', 'upload'])
    def test_step_upload(self):
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_not_called()
        refine_mock.run_refinement_pipeline.assert_not_called()
        convert_mock.convert_md_to_json_structure.assert_not_called()
        upload_mock.run_upload_pipeline.assert_called_once()

    @patch('sys.argv', ['main.py', '--step', 'all'])
    def test_step_all(self):
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_called_once()
        refine_mock.run_refinement_pipeline.assert_called_once()
        convert_mock.convert_md_to_json_structure.assert_called_once()
        upload_mock.run_upload_pipeline.assert_called_once()

    @patch('sys.argv', ['main.py'])
    def test_no_args_runs_all(self):
        # Default behavior should probably be 'all' for backward compatibility
        orchestrator.main()
        ingest_mock.run_batch_processing.assert_called_once()
        refine_mock.run_refinement_pipeline.assert_called_once()
        convert_mock.convert_md_to_json_structure.assert_called_once()
        upload_mock.run_upload_pipeline.assert_called_once()

if __name__ == '__main__':
    unittest.main()
