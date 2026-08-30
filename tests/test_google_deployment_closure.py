import importlib
import os
from pathlib import Path
import tomllib
import unittest
from datetime import datetime, timezone

from poiex_runtime.store import MemoryStore


ROOT = Path(__file__).resolve().parents[1]


class GoogleDeploymentClosureTests(unittest.TestCase):
    def test_required_google_runtime_dependencies_are_not_optional(self):
        data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        deps = data['project']['dependencies']
        joined = '\n'.join(deps)
        self.assertRegex(joined, r'google-adk\[[^\]]*\bgcp\b')
        self.assertIn('google-cloud-firestore', joined)
        self.assertIn('fastapi', joined)
        self.assertIn('uvicorn', joined)

    def test_owner_closure_scripts_exist(self):
        required = [
            'scripts/google_cloudshell_bootstrap.sh',
            'scripts/google_owner_preflight.sh',
            'scripts/google_prepare_project.sh',
            'scripts/google_deploy_cloud_run.sh',
            'scripts/google_capture_evidence.sh',
            'scripts/google_run_deployed_eval.sh',
            'scripts/github_publish_new_repo.sh',
        ]
        for rel in required:
            path = ROOT / rel
            self.assertTrue(path.exists(), rel)
            self.assertTrue(os.access(path, os.X_OK), rel)


    def test_project_name_fits_agents_cli_limit_and_matches_manifest(self):
        data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        name = data['project']['name']
        self.assertLessEqual(len(name), 26)
        manifest = (ROOT / 'agents-cli-manifest.yaml').read_text(encoding='utf-8')
        self.assertIn(f'name: {name}\n', manifest)

    def test_project_build_declares_explicit_package_discovery(self):
        data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        find = data.get('tool', {}).get('setuptools', {}).get('packages', {}).get('find', {})
        self.assertEqual(['app*', 'control_service*', 'poiex_runtime*'], find.get('include'))

    def test_default_gemini_model_is_contest_eligible(self):
        import re
        source = (ROOT / 'poiex_runtime' / 'adk_planner.py').read_text(encoding='utf-8')
        m = re.search(r'DEFAULT_GEMINI_MODEL\s*=\s*os\.getenv\(\s*"GEMINI_MODEL",\s*"([^"]+)"', source)
        self.assertIsNotNone(m, "DEFAULT_GEMINI_MODEL fallback not found")
        default_model = m.group(1)
        # Contest requires a Gemini >= 3.5 route. Reject the 1.5/2.x legacy fallbacks.
        self.assertRegex(default_model, r'^gemini-([3-9]|\d{2,})', default_model)
        self.assertNotIn('2.5', default_model)
        self.assertNotIn('1.5', default_model)

    def test_deploy_binds_contest_model_and_locks_privileged_control(self):
        source = (ROOT / 'scripts' / 'google_deploy_cloud_run.sh').read_text(encoding='utf-8')
        # Contest-eligible model + global GenAI location (only route that serves >=3.5 here).
        self.assertRegex(source, r'GEMINI_MODEL="\$\{GEMINI_MODEL:-gemini-3\.7-flash\}"')
        self.assertRegex(source, r'GENAI_LOCATION="\$\{GENAI_LOCATION:-global\}"')
        self.assertNotIn('GEMINI_MODEL=gemini-2.5-flash', source)
        self.assertNotIn('GEMINI_MODEL=gemini-1.5-flash', source)
        # The privileged control plane must never be publicly invocable.
        control_block = source.split('deploy deterministic GOC control', 1)[1]
        self.assertIn('--no-allow-unauthenticated', control_block)
        self.assertNotIn('--allow-unauthenticated"', control_block)
        # allUsers may reach the advisory fleet (demo surface) but never the control plane.
        self.assertNotRegex(
            source,
            r'add-iam-policy-binding\s+"\$CONTROL_SERVICE".*allUsers',
        )

    def test_owner_preflight_uses_current_agents_cli_interface(self):
        path = ROOT / 'scripts' / 'google_owner_preflight.sh'
        source = path.read_text(encoding='utf-8')
        self.assertNotIn('cmd-info', source)
        self.assertIn('agents-cli info --json', source)
        self.assertIn('agents-cli login --status', source)

    def test_cloudshell_bootstrap_exists_and_defaults_fail_closed_to_plan(self):
        path = ROOT / 'scripts' / 'google_cloudshell_bootstrap.sh'
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        source = path.read_text(encoding='utf-8')
        self.assertIn('MODE="--plan"', source)
        self.assertIn('--project', source)
        self.assertIn('--region', source)
        self.assertIn('gcloud config get-value project', source)
        self.assertIn('google_prepare_project.sh', source)
        self.assertIn('--plan', source)
        self.assertIn('google_deploy_cloud_run.sh', source)
        self.assertIn('--dry-run', source)

    def test_cloudshell_apply_bootstraps_agents_cli_without_embedding_credentials(self):
        path = ROOT / 'scripts' / 'google_cloudshell_bootstrap.sh'
        source = path.read_text(encoding='utf-8')
        self.assertIn('google-agents-cli', source)
        self.assertIn('agents-cli login --status', source)
        self.assertIn('agents-cli login -i', source)
        self.assertIn('google_prepare_project.sh', source)
        self.assertIn('--apply', source)
        self.assertIn('google_deploy_cloud_run.sh', source)
        self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS=', source)
        self.assertNotIn('sk-', source)

    def test_cloudshell_execution_doc_exists(self):
        path = ROOT / 'docs' / 'GOOGLE_CLOUDSHELL_ONE_ENTRY_V0_1.md'
        self.assertTrue(path.exists())
        text = path.read_text(encoding='utf-8')
        self.assertIn('google_cloudshell_bootstrap.sh --plan', text)
        self.assertIn('google_cloudshell_bootstrap.sh --apply', text)
        self.assertIn('LOCAL_PLAN != CLOUD_DEPLOYMENT', text)


    def test_deployment_scaffolding_occurs_in_disposable_git_worktree(self):
        path = ROOT / 'scripts' / 'google_deploy_cloud_run.sh'
        source = path.read_text(encoding='utf-8')
        self.assertIn('git worktree add --detach', source)
        self.assertIn('DEPLOY_WORKTREE', source)
        self.assertIn('git status --porcelain', source)
        self.assertIn('uv run python -m unittest discover', source)
        self.assertIn('scaffold_diff.patch', source)
        self.assertIn('git worktree remove --force', source)


    def test_generated_google_closure_artifacts_do_not_dirty_canonical_repo(self):
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('artifacts/google_closure/', ignore)

    def test_cloud_demo_cases_are_governed(self):
        module = importlib.import_module('poiex_runtime.cloud_demo')
        now = datetime(2026, 8, 27, 17, 30, tzinfo=timezone.utc)

        allow_store = MemoryStore()
        allowed = module.run_demo_case(
            allow_store,
            case='allow',
            now=now,
            scenario_id='unit-allow',
        )
        self.assertEqual('ALLOW', allowed['decision'])
        self.assertEqual('PASS', allowed['replay'])
        self.assertEqual(1, allow_store.synthetic_mutation_count)

        revoked_store = MemoryStore()
        revoked = module.run_demo_case(
            revoked_store,
            case='revoked_authority',
            now=now,
            scenario_id='unit-revoked',
        )
        self.assertEqual('BLOCK', revoked['decision'])
        self.assertIn('AUTHORITY_REVOKED', revoked['reasons'])
        self.assertEqual(0, revoked_store.synthetic_mutation_count)

        substitution_store = MemoryStore()
        substitution = module.run_demo_case(
            substitution_store,
            case='target_substitution',
            now=now,
            scenario_id='unit-target',
        )
        self.assertEqual('REJECTED_BEFORE_INTENT', substitution['decision'])
        self.assertEqual(0, substitution_store.synthetic_mutation_count)

    def test_control_service_is_synthetic_only_and_store_factory_bound(self):
        path = ROOT / 'control_service' / 'main.py'
        self.assertTrue(path.exists())
        source = path.read_text(encoding='utf-8')
        self.assertIn('build_store_from_env', source)
        self.assertIn('SYNTHETIC_DEMO_ONLY', source)
        self.assertNotIn('subprocess.', source)
        self.assertNotIn('os.system(', source)

    def test_control_service_local_http_contract_and_cloud_fail_closed(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from control_service.main import app

        client = TestClient(app)
        with patch.dict(os.environ, {"POIEX_GOC_STORE": "memory"}, clear=True):
            health = client.get('/healthz')
            self.assertEqual(200, health.status_code)
            self.assertEqual('SYNTHETIC_DEMO_ONLY', health.json()['truth_ceiling'])
            allow = client.post('/v1/demo/run', json={
                'case': 'allow', 'scenario_id': 'http-allow'
            })
            self.assertEqual(200, allow.status_code)
            self.assertEqual('ALLOW', allow.json()['decision'])

        with patch.dict(os.environ, {
            "K_SERVICE": "poiex-goc-control",
            "POIEX_GOC_STORE": "memory",
        }, clear=True):
            blocked = client.post('/v1/demo/run', json={
                'case': 'allow', 'scenario_id': 'cloud-memory-block'
            })
            self.assertEqual(400, blocked.status_code)
            self.assertIn('POIEX_GOC_STORE=firestore', blocked.json()['detail'])


if __name__ == '__main__':
    unittest.main()
