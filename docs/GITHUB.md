# GitHub repository presentation

## Suggested metadata

**Description**

> Open-source autonomous AI agent framework for Minecraft — design, plan, navigate, build, observe and verify.

**Topics**

```text
minecraft
minecraft-mod
fabric
ai
ai-agent
autonomous-agent
minecraft-bot
baritone
procedural-generation
automation
open-source
```

Apply these settings only to the existing, confirmed BlockMind repository. Do not create a second repository to work around a missing remote.

## Workflow badge

The repository includes `.github/workflows/ci.yml`, which runs Core tests and the Fabric build. Add the standard GitHub Actions workflow badge to both READMEs after the correct `owner/BlockMind` remote is known and the first workflow run has produced a real status. Until then, do not display a fabricated passing badge.

## Release policy for the current stage

The repository is **Early Development / Experimental**. Do not create a GitHub Release, publish a stable version, or advertise BlockMind as fully functional until a person has verified:

- the real Minecraft connection;
- real movement and block placement;
- real Baritone navigation;
- pause, resume, stop, and emergency stop;
- failure recovery;
- the complete live acceptance build.

Verified screenshots and GIFs belong in `docs/assets/` with the commit and environment recorded.
