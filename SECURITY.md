# Security and Private Data

This is a public source repository. Production projects, personal media, credentials, and model runtimes belong outside it.

Do not commit:

- API keys, tokens, cookies, credentials, or `.env` files;
- raw or cloned voice samples and private transcripts; the explicitly authorized Foxjiu reference rule and its fixed transcript are the documented exception, not permission to publish audio;
- client manuscripts, unreleased footage, recordings, exports, or Jianying/CapCut projects;
- model weights, caches, generated media, contact sheets, or run directories;
- machine-specific absolute paths containing a personal username.

Use synthetic or sanitized fixtures when a bug requires an example. Avoid attaching production approval ledgers, local absolute paths, download cookies, or unredacted environment dumps to public issues. Keep the fixed reference audio on the authorized machine; missing audio must not be replaced by another speaker or a cropped previous master.

`tools/validate_skills.py` checks publication file types, source size, local links, JSON/YAML, selected personal-home path patterns, and the fixed review UI hashes. It is not a complete secret scanner. `.gitignore` does not protect a file already tracked or force-added to Git. Review `git diff --cached` before publishing.

The skill installer previews by default and refuses existing destinations. Backups of installed skills belong outside discovery directories; do not overwrite personal modifications just to complete an update. Production approvals remain bound to the project artifacts even after the repository is upgraded.

Report a suspected exposure privately to the repository owner; do not post credentials or private media in a public issue. Revoke or rotate exposed credentials first, then coordinate removal from the tree and history. History rewriting and destructive cleanup require their own scoped authorization. Report only sanitized details publicly after the exposure has been handled.
