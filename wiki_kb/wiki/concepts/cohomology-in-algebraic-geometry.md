---
sources: ["summaries/01_英文数学_Algebraic Geometry (Robin Hartshorne).md"]
brief: "Cohomology measures global sheaf data via derived functors and vanishing."
---

# Cohomology in Algebraic Geometry

Cohomology is one of the central tools in modern algebraic geometry. It turns local geometric and algebraic data, encoded in sheaves, into global invariants that control sections, divisors, morphisms, and deformation behavior.

In [[summaries/01_英文数学_Algebraic Geometry (Robin Hartshorne)]], cohomology appears as a major organizing principle of the book: it is introduced after schemes and sheaves, then used to prove vanishing theorems, Serre duality, the cohomology of projective space, the formal functions theorem, semicontinuity, and base change. It is also essential in the study of divisors and line bundles, especially through the relation between invertible sheaves and linear systems.

## Core idea

The basic philosophy is that a sheaf 20 on a space X contains local information, but its cohomology groups

- H74(X, 20) describe global sections and obstructions,
- higher H74 measure the failure of local data to glue globally,
- and vanishing results often imply strong geometric consequences.

In Hartshorne's treatment, cohomology is defined as the right derived functors of global sections. This makes the theory flexible and powerful, and it fits naturally into the language of homological algebra.

## Main constructions

### Derived functors

Cohomology is built from the global section functor Gamma(X, -). Since this functor is left exact but not exact, its right derived functors produce the cohomology groups:

- H72(X, 20) = 72-th right derived functor of global sections.

This is developed using injective resolutions and universal delta-functors. The derived-functor approach gives the formal properties needed for long exact sequences, functoriality, and compatibility with morphisms.

### Sheaf cohomology

For sheaves on a topological space or on a scheme, sheaf cohomology is the primary invariant. Important facts include:

- injective sheaves are acyclic,
- flasque sheaves are acyclic,
- cohomology can be computed using flasque resolutions,
- on noetherian affine schemes, higher cohomology of quasi-coherent sheaves vanishes.

This last point is fundamental: it shows that affines are cohomologically simple, and it underlies many gluing arguments in algebraic geometry.

### Cech cohomology

Hartshorne also discusses Cech cohomology as a computational tool. It is especially useful for explicit calculations on projective space and for comparing local and global sections. In many noetherian separated settings, Cech cohomology agrees with derived-functor cohomology for quasi-coherent sheaves.

## Key results in the book

### Cohomology of projective space

One of the most important calculations in the book is the cohomology of the twisting sheaves O(n) on projective space. This result drives much of the later theory.

It shows that:

- He(X, O(n)) is the expected homogeneous piece,
- intermediate cohomology vanishes,
- top cohomology is nonzero in the expected degree,
- and there is a duality pairing between low and top cohomology.

These computations are used repeatedly in later chapters, especially for divisors, projective morphisms, and duality.

### Serre vanishing and ampleness

A key theme is that sufficiently positive line bundles have vanishing higher cohomology after enough twisting. This is the cohomological characterization of ampleness in [[concepts/divisors-and-line-bundles]].

In particular, for a coherent sheaf 20 on a projective scheme, large positive twists often satisfy:

- H72(X, 20(n)) = 0 for i > 0 and n 22 0.

This is one of the main bridges between cohomology and projective geometry.

### Serre duality

Cohomology becomes especially powerful through duality. Hartshorne develops Serre duality for projective schemes, showing that top cohomology pairs perfectly with Hom into a dualizing sheaf. On smooth projective varieties, this becomes a geometric duality involving the canonical sheaf.

This gives a cohomological explanation of classical results such as Riemann-Roch on curves and surfaces.

### Theorem on formal functions

Cohomology also controls formal neighborhoods. The theorem on formal functions identifies completed higher direct images with inverse limits of cohomology of infinitesimal thickenings. This is a major technical tool used in the proof of Zariski's Main Theorem and in Stein factorization.

### Semicontinuity and base change

A major later use of cohomology is in families. The semicontinuity theorem shows that fiber cohomology dimensions vary upper semicontinuously in flat projective families. The cohomology-and-base-change theorem then describes when cohomology commutes with taking fibers.

These results explain why cohomology is one of the main tools for studying moduli and deformation problems.

## Why cohomology matters geometrically

Cohomology provides several kinds of information at once:

- **existence of sections**: He(X, 20) measures global sections,
- **obstructions**: H71 often governs extension and gluing problems,
- **classification data**: cohomology helps define invariants like the Picard group, arithmetic genus, and geometric genus,
- **duality**: top cohomology encodes canonical information,
- **families**: cohomology detects how geometry changes in parameter spaces.

In Hartshorne's book, many classical geometric statements are rephrased cohomologically so they can be proved cleanly and generalized.

## Related concepts

- [[concepts/schemes]] for the ambient language in which sheaves and cohomology are defined
- [[concepts/divisors-and-line-bundles]] for the geometric meaning of cohomology of invertible sheaves
- [[summaries/01_英文数学_Algebraic Geometry (Robin Hartshorne)]] for the full source document and chapter structure

## In Hartshorne's development

The book uses cohomology to move from local geometry to global structure:

1. define sheaves and schemes,
2. build cohomology as derived functors,
3. compute it in basic cases,
4. use it to prove vanishing theorems,
5. apply it to duality, flatness, formal completion, and families.

This makes cohomology not just a technical tool but a unifying language for the whole text.