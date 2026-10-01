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

The confirmed repository is [BADMAAAN/BlockMind](https://github.com/BADMAAAN/BlockMind). `.github/workflows/ci.yml` runs Core tests and six Fabric build/test jobs. Add a workflow badge only after a real run has produced a status; do not fabricate a passing badge. CI builds do not prove runtime acceptance.

## Release policy for the current stage

The repository is **Early Development / Experimental**. Do not create a GitHub Release, publish a stable version, or advertise BlockMind as fully functional until a person has verified:

- the real Minecraft connection;
- real movement and block placement;
- real Baritone navigation;
- pause, resume, stop, and emergency stop;
- failure recovery;
- the complete live acceptance build.

Verified screenshots and GIFs belong in `docs/assets/` with the commit and environment recorded.
