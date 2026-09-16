"""Regression checks for publication inputs and non-destructive installation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check
import doctor
import install_skills
import validate_skills as validator


class RepositoryToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')
        return path

    def catalog(self):
        self.write('skill_catalog.json', json.dumps({'schema_version': 1, 'production': ['alpha', 'beta'], 'compatibility': ['gamma']}))
        for name in ('alpha', 'beta', 'gamma'):
            self.write(f'skills/{name}/SKILL.md', f'---\nname: {name}\ndescription: A test skill\n---\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)

    def test_yaml_multiline_description_supported(self):
        path = self.write('SKILL.md', '---\nname: example\ndescription: >-\n  Use for examples\n  with text\n---\n')
        self.assertEqual(validator.parse_frontmatter(path)['description'], 'Use for examples with text')

    def test_duplicate_yaml_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validator.load_yaml('name: one\nname: two\n')

    def test_prompt_must_mention_skill_in_prompt_field(self):
        skill = self.root / 'skills/example'
        self.write('skills/example/agents/openai.yaml', 'interface:\n  display_name: "$example"\n  short_description: "Example"\n  default_prompt: "Do the work"\n')
        self.assertTrue(any('default_prompt must mention' in error for error in validator.validate_agent_yaml(skill, 'example', self.root)))

    def test_links_check_supporting_docs_and_skip_code_examples(self):
        self.write('target file.md', 'exists')
        doc = self.write('guide.md', '[file](<target file.md>)\n[file](target%20file.md#heading)\n[remote](https://example.com)\n```md\n[example](missing.md)\n```\n')
        self.assertEqual(validator.validate_links(doc, self.root), [])
        doc.write_text('[broken](absent.md)\n[escape](../outside.md)', encoding='utf-8')
        self.assertEqual(len(validator.validate_links(doc, self.root)), 2)

    def test_git_ignores_local_bytecode_but_rejects_forced_tracked_bytecode(self):
        self.git('init', '-q')
        self.write('.gitignore', '__pycache__/\n*.pyc\n')
        cache = self.write('skills/example/__pycache__/example.pyc', 'cache')
        self.assertNotIn(cache, validator.source_files(self.root))
        self.git('add', '-f', str(cache))
        self.assertTrue(any('must not be committed' in error for error in validator.validate_repository_files(self.root)))

    def test_root_and_web_assets_checked_for_private_home_paths(self):
        private_path = '/' + 'Users/' + 'private-person/file'
        for name in ('README.md', 'assets/app.js', 'assets/view.html'):
            self.write(name, private_path)
        self.assertEqual(len(validator.validate_repository_files(self.root)), 3)

    def test_documentation_placeholders_remain_allowed(self):
        self.write('README.md', '`/Users/<name>` and `$HOME` are placeholders.\n')
        self.assertEqual(validator.validate_repository_files(self.root), [])

    def test_invalid_or_duplicate_data_is_rejected(self):
        self.write('manifest.json', '{"passed": true, "passed": false}')
        self.assertTrue(validator.validate_repository_files(self.root))
        self.write('manifest.json', '{}')
        self.write('agents.yaml', 'interface: [unterminated')
        self.assertTrue(validator.validate_repository_files(self.root))

    def test_tracked_sensitive_files_are_rejected(self):
        self.git('init', '-q')
        self.write('.gitignore', '.env\n*.WAV\n*.pt\n')
        for name in ('.env', 'private.WAV', 'model.pt'):
            path = self.write(name, 'synthetic fixture')
            self.git('add', '-f', str(path))
        self.assertEqual(len(validator.validate_repository_files(self.root)), 3)

    def test_catalog_requires_complete_unique_package_membership(self):
        self.catalog()
        self.assertEqual(validator.validate_catalog(self.root, {'alpha', 'beta', 'gamma'}), [])
        self.assertTrue(validator.validate_catalog(self.root, {'alpha', 'beta'}))

    def test_frozen_review_assets_cannot_drift(self):
        folder = 'skills/zhangyanfa-track-design/assets/review-ui-v1/'
        hashes = {}
        for name in ('index.html', 'review.css', 'review.js'):
            path = self.write(folder + name, name)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write(folder + 'framework_manifest.json', json.dumps({'framework_id': 'foxjiu-review-ui-v1', 'sha256': hashes}))
        self.assertEqual(validator.validate_frozen_ui(self.root), [])
        self.write(folder + 'review.js', 'unapproved change')
        self.assertTrue(validator.validate_frozen_ui(self.root))

    def test_install_preview_creates_nothing(self):
        self.catalog()
        destination = self.root / 'new-install'
        result = install_skills.install(self.root, destination, 'production', 'copy', False)
        self.assertEqual(len(result), 2)
        self.assertFalse(destination.exists())

    def test_install_detects_late_collision_before_any_copy(self):
        self.catalog()
        self.write('install/beta/SKILL.md', 'existing personal skill')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            install_skills.install(self.root, self.root / 'install', 'production', 'copy', True)
        self.assertFalse((self.root / 'install/alpha').exists())
        self.assertEqual((self.root / 'install/beta/SKILL.md').read_text(), 'existing personal skill')

    def test_copy_has_selected_packages_and_no_cache(self):
        self.catalog()
        self.write('skills/alpha/__pycache__/test.pyc', 'cache')
        install_skills.install(self.root, self.root / 'install', 'production', 'copy', True)
        self.assertTrue((self.root / 'install/alpha/SKILL.md').is_file())
        self.assertFalse((self.root / 'install/alpha/__pycache__').exists())
        self.assertFalse((self.root / 'install/gamma').exists())

    def test_symlink_install_is_idempotent_but_other_link_blocks(self):
        self.catalog()
        destination = self.root / 'install'
        install_skills.install(self.root, destination, 'all', 'symlink', True)
        result = install_skills.install(self.root, destination, 'all', 'symlink', True)
        self.assertTrue(all('already linked' in line for line in result))
        (destination / 'alpha').unlink()
        (destination / 'alpha').symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            install_skills.install(self.root, destination, 'all', 'symlink', True)

    def test_install_cannot_target_sources_or_import_external_symlink(self):
        self.catalog()
        with self.assertRaisesRegex(ValueError, 'overlap'):
            install_skills.install(self.root, self.root / 'skills', 'production', 'copy', True)
        (self.root / 'skills/alpha/outside').symlink_to(self.root / 'other')
        with self.assertRaisesRegex(ValueError, 'contains a symlink'):
            install_skills.install(self.root, self.root / 'install', 'production', 'copy', True)

    def test_catalog_path_traversal_rejected(self):
        self.write('skill_catalog.json', json.dumps({'schema_version': 1, 'production': ['../escape']}))
        with self.assertRaisesRegex(ValueError, 'invalid skill name'):
            install_skills.selected_skills(self.root, 'production')

    def test_required_dependency_failure_is_visible(self):
        with patch.object(doctor.shutil, 'which', return_value=None):
            self.assertFalse(doctor.command_check('ffprobe', ['-version'])['ok'])
        with patch.object(doctor.importlib.metadata, 'version', return_value='10.0.0'):
            self.assertFalse(doctor.package_check('Pillow', (12, 3, 0), 13)['ok'])

    def test_cli_discovery_ignores_helpers_and_tests(self):
        helper = self.write('helper.py', 'def helper(): pass\n')
        cli = self.write('cli.py', 'if __name__ == "__main__":\n    pass\n')
        test = self.write('test_cli.py', cli.read_text())
        self.assertFalse(check.has_cli(helper))
        self.assertFalse(check.has_cli(test))
        self.assertTrue(check.has_cli(cli))

    def test_check_runner_propagates_failed_command(self):
        with self.assertRaisesRegex(RuntimeError, 'exit 3'):
            check.run([sys.executable, '-c', 'raise SystemExit(3)'], dict(os.environ), quiet=True)


if __name__ == '__main__':
    unittest.main()
