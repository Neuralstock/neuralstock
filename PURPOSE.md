# NeuralStock Purpose

## In one sentence

NeuralStock exists to make high-quality, adaptable 3D building blocks as open, dependable, and easy to use as open-source software packages—for both people and autonomous agents.

## The problem

Turning an idea into an interactive 3D world is still unnecessarily difficult.

Creators can describe what they want, write application code, and assemble a Three.js scene quickly, but useful 3D assets remain a bottleneck. Existing assets are scattered across marketplaces and archives, carry inconsistent license terms, use incompatible formats, lack trustworthy metadata, or arrive only as baked meshes that are difficult to adapt.

This is especially limiting for AI agents. An agent may be able to write an application, but it cannot reliably discover whether an asset:

- is safe for unrestricted commercial use;
- has the correct real-world dimensions and orientation;
- fits a polygon, texture, or performance budget;
- includes collision geometry and meaningful attachment points;
- can be changed without directly editing vertices;
- was built reproducibly from an inspectable source;
- will behave correctly in a browser or game engine.

Without that information, agents waste tokens and compute recreating ordinary objects, produce inconsistent geometry, or stop at crude primitives. Human creators lose time to the same search, conversion, cleanup, licensing, and integration work.

The missing piece is not another gallery of downloadable models. It is an open, machine-readable supply chain for 3D assets.

## The mission

NeuralStock will build a public CC0 registry of production-ready Blender assets that can be discovered, understood, modified, built, and consumed through stable machine interfaces.

Every asset should provide two equally important forms:

1. An editable Blender source that preserves useful structure such as Geometry Nodes, modifiers, materials, parameters, anchors, and generation logic.
2. A validated runtime artifact, initially GLB, that can be loaded immediately by Three.js, game engines, simulators, and other 3D runtimes.

Semantic metadata and reproducible build receipts connect those forms. An agent should be able to ask for an object, evaluate whether it fits the task, supply safe parameter overrides, and receive a verified artifact without manually manipulating mesh vertices.

## The core promise

For every published asset, NeuralStock aims to provide:

- **Freedom:** CC0 asset content with no commercial-use restriction or attribution dependency.
- **Source:** the editable `.blend`, not only a flattened export.
- **Readiness:** a validated web- and engine-ready `.glb`.
- **Legibility:** structured metadata describing dimensions, materials, geometry budgets, anchors, collisions, capabilities, and parameters.
- **Adaptability:** declared, bounded inputs that agents and creators can change safely.
- **Provenance:** durable evidence of where the asset came from and why its license is trusted.
- **Reproducibility:** enough build information to regenerate and verify published outputs.
- **Portability:** open schemas, downloadable snapshots, content hashes, and artifacts that can be mirrored without permission.

## Who NeuralStock serves

### Independent creators

People building games, visualizations, educational tools, prototypes, portfolios, and spatial interfaces should be able to move from an idea to a credible scene without becoming experts in asset licensing and Blender cleanup.

### Autonomous agents

Agents need a dependable vocabulary of real objects. NeuralStock should let them search by meaning and constraints, compose scenes, customize procedural sources, and validate outputs through tools rather than guesswork.

### Studios and technical teams

Game studios, simulation teams, researchers, synthetic-data pipelines, robotics developers, and enterprise visualization teams need assets that can enter commercial and automated workflows without accumulating attribution obligations or uncertain provenance.

### Open-source asset creators

Artists and procedural-model authors should have a respected place to contribute reusable work, improve shared standards, and see their assets become infrastructure for many downstream projects.

## The change we want to create

NeuralStock should shorten the path from intent to a functioning 3D experience.

```text
Open Blender sources
        +
trusted licenses and provenance
        +
machine-readable capabilities
        +
reproducible runtime builds
        |
        v
agents and creators spend less effort rebuilding ordinary objects
        |
        v
more ideas reach playable, testable, and commercially usable form
```

The substantive impact is not merely a larger asset count. It is reduced friction across the entire creation loop:

- fewer tokens spent generating commonplace geometry;
- less time spent searching, converting, and repairing assets;
- fewer legal questions during commercial adoption;
- more consistent spatial and physical behavior;
- faster prototyping for people without specialist 3D skills;
- better training and simulation inputs with inspectable provenance;
- a shared asset vocabulary that improves as every contributor and agent builds on it.

## Product principles

### 1. Freedom is part of the data model

License status is not a disclaimer attached after publication. It is a required, validated property of every asset and every dependency. Asset content uses CC0 or reviewed equivalent public-domain status; software tooling may use a permissive software license such as MIT.

### 2. The source is part of the product

A runtime mesh alone cannot preserve the knowledge embedded in a well-made Blender file. Modifiers, Geometry Nodes, material graphs, anchors, and semantic structure should remain available whenever they add reuse value.

### 3. Assets must be legible to machines

Names and thumbnails are insufficient. Agents need explicit units, coordinate conventions, dimensions, constraints, affordances, parameter types, compatibility, and performance characteristics.

### 4. Structured truth comes before generated confidence

Exact constraints such as license, size, triangle count, and engine compatibility must be deterministically filterable. Semantic or AI-assisted search may help discover candidates, but it must not override verified facts.

### 5. Trust must be reproducible

Published outputs should be tied to source hashes, tool versions, build parameters, validation reports, and provenance records. A successful build is evidence, not an opaque upload.

### 6. Quality matters more than raw volume

One dependable, adaptable table is more useful than hundreds of uncertain meshes. The registry should reward completeness, correctness, interoperability, and reuse rather than collection size alone.

### 7. Composition matters more than isolated beauty

Assets should work together. Shared units, origins, naming, materials, anchors, collisions, LOD conventions, and runtime profiles are central to the project.

### 8. Automation must preserve safety

Agent-generated and contributor-supplied Blender content is untrusted until inspected. Automated growth must never bypass license review, sandboxing, validation, or publication gates.

### 9. The commons must remain forkable

The hosted NeuralStock service should be the easiest way to use the registry, not the only way. Public schemas, immutable artifacts, build tooling, and complete snapshots must allow independent clients and mirrors.

### 10. Sustainability must not revoke freedom

Future revenue may come from convenience, hosted build compute, private workflows, higher service limits, or enterprise support. It must not place already-published public assets behind restrictive terms or make their core usefulness depend on a proprietary client.

## What NeuralStock is not

NeuralStock is not:

- a conventional marketplace built around per-asset transactions;
- a scrape of files whose provenance cannot be demonstrated;
- a static thumbnail gallery with an API added afterward;
- an opaque text-to-3D generator;
- a replacement for Blender, artists, or specialist asset creation;
- a promise that every asset is appropriate for every runtime;
- a centralized gatekeeper that prevents the public collection from being mirrored or extended.

It is shared infrastructure that makes existing and newly created open 3D work dramatically easier to trust and reuse.

## How we will recognize success

Asset count alone is not the north-star metric. NeuralStock is succeeding when:

- a creator or agent can move from a semantic request to a correctly placed runtime asset with minimal integration work;
- published assets consistently reproduce from their declared sources and build inputs;
- commercial teams can adopt assets without case-by-case license investigation;
- parameterized assets are reused in meaningfully different scenes instead of repeatedly rebuilt;
- registry queries reliably enforce physical, legal, and performance constraints;
- external tools, engines, agents, and mirrors implement the public contract;
- contributors can take an asset from upload to validated publication with little repetitive manual work;
- improvements to schemas and tooling raise the quality of the whole collection, not only one hosted application.

The project should track time-to-first-valid-asset, successful build rate, reproducibility rate, provenance rejection rate, asset reuse, parameterized-build reuse, runtime compatibility, and the number of independent consumers or mirrors.

## Initial focus

The first milestone is intentionally small: a coherent set of 15–20 essential assets that proves the complete contract.

That collection should demonstrate:

- CC0 provenance;
- synchronized Blender source and GLB runtime artifacts;
- real-world dimensions and consistent coordinates;
- anchors and collision metadata;
- mesh, material, and texture inspection;
- at least several useful procedural parameter interfaces;
- reproducible headless builds;
- clean consumption from a simple Three.js client and an agent-facing query interface.

The first collection is not the destination. It is the test fixture for proving that a trustworthy, self-improving open 3D ecosystem can work.

## North star

An idea should not stall because its creator—or the agent helping them—cannot find a trustworthy chair, tree, door, road, tool, or table.

NeuralStock exists so the ordinary building blocks of virtual worlds become a shared public resource: free to use, simple to understand, safe to automate, and open to improve.
