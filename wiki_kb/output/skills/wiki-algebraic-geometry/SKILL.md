---
name: wiki-algebraic-geometry
description: Use when reasoning about schemes, divisors/line bundles/Picard groups, cohomology, projective embeddings, or birational geometry in the style of Hartshorne; not for commutative algebra alone or general topology.
---

# Wiki Algebraic Geometry

This skill encodes the Hartshorne-style worldview of algebraic geometry: start from local affine data, glue to schemes, and then use divisors, line bundles, and cohomology to control global geometry. It is for answering concrete questions the way an algebraic geometer would: what does a morphism really mean on coordinate rings or stalks, when does a line bundle define an embedding, how do divisors move under blow-ups, and what cohomological vanishing or duality says about a family or a curve.

## When to use this skill

Use this skill when the question is about:

- deciding whether a map of varieties/schemes is a morphism, immersion, proper, flat, smooth, or birational
- understanding a divisor, principal divisor, Cartier vs. Weil divisor, or Picard/class group question
- checking whether a line bundle is ample/very ample or whether sections define a projective embedding
- computing or interpreting sheaf cohomology, Serre duality, formal functions, or base change
- reasoning about curves, surfaces, blow-ups, exceptional curves, and resolution of singularities in the Hartshorne tradition
- translating between geometric statements and ringed-space / local-ring language

Not for:

- pure commutative algebra questions with no geometric layer
- general topology or differential geometry outside algebraic/analytic comparison
- basic ring computations that do not touch schemes, divisors, or cohomology
- moduli theory in full generality unless it is being used through the curve/surface/Hartshorne lens

## Core decision rules

- **When a question is about a variety or scheme, reduce it to affine charts and stalks first** — schemes are local-ringed spaces; the right test is usually on Spec of rings or on local neighborhoods.
- **If a morphism is suspected, check the pullback on regular functions before the point-set map** — in algebraic geometry, the ring map and stalk map often determine the geometry; ignoring them loses the structure.
- **When codimension-one data is involved, think divisors and line bundles together** — Weil/Cartier divisors, invertible sheaves, and the Picard group are different languages for the same geometry in favorable cases.
- **If you need to know whether a line bundle gives a map to projective space, ask whether it is globally generated or very ample** — base-point freeness gives a morphism, very ampleness gives a closed immersion.
- **When a geometric statement sounds global, look for a cohomology vanishing or duality statement** — vanishing controls sections, obstructions, and embeddings; Serre duality and Riemann–Roch convert geometry into numerical data.
- **For curves, use function fields and divisors aggressively** — birational classification, rational maps, and line bundles on curves are best understood through degree, principal divisors, and the function field.
- **For surfaces, expect blow-ups and intersection theory to do the heavy lifting** — birational maps factor through monoidal transformations, and self-intersection/exceptional curves often decide what can be contracted.
- **When a family varies, test flatness before trusting fiberwise intuition** — constancy of Hilbert polynomial, fiber dimension, and cohomology base change are the reliable invariants in families.
- **If a statement mentions singularities, switch to local algebra or differentials** — regularity, the Jacobian criterion, \Omega, and completions are the standard diagnostics.
- **When projective geometry is in play, expect degree and Hilbert polynomial to govern the numerics** — degree is not just counting intersections; it is encoded by the homogeneous coordinate ring.
- **If a map is only rational, ask where it is undefined and whether blow-up resolves it** — indeterminacy loci and strict transforms are the standard way to make rational maps honest.
- **When you see 'proper' or 'separated', test the valuative criterion mindset** — algebraic geometry often decides these properties by how maps behave over valuation rings.

## Approach

1. Identify the geometric object: affine variety, projective variety, scheme, curve, surface, or family.
2. Translate the question into the local language: rings, stalks, divisors, or sheaves.
3. Decide which invariant is the right one: divisor class, degree, cohomology, flatness, or intersection number.
4. Use the Hartshorne-style theorem that fits the shape: Nullstellensatz, Serre vanishing, Riemann-Roch, duality, semicontinuity, blow-up universal property, or valuative criterion.
5. Convert the conclusion back into a geometric statement about maps, embeddings, fibers, or birational models.

## References

- [[references/hartshorne-roadmap]]

## Known gaps

- The wiki is centered heavily on Hartshorne’s *Algebraic Geometry* and does not cover the full modern stack-theoretic or derived-scheme viewpoint.
- It gives strong coverage of curves, surfaces, divisors, sheaves, cohomology, and classical birational geometry, but much less on explicit computational algebraic geometry.
- It does not attempt a comprehensive treatment of arithmetic geometry beyond the Weil conjectures, elliptic curves, and finite-field cohomology themes present in the source.
