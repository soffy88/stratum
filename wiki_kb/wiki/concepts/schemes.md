---
sources: ["summaries/01_英文数学_Algebraic Geometry (Robin Hartshorne).md"]
brief: "Schemes are locally ringed spaces built from prime spectra and glued affine pieces."
---

# Schemes and Locally Ringed Spaces

Schemes are the central geometric objects in modern algebraic geometry. In Hartshorne’s presentation, they are built by first defining **locally ringed spaces** and then showing how affine schemes arise from rings via the spectrum construction. The key idea is that geometry is encoded not only by a topological space, but also by a sheaf of rings whose stalks are local rings.

## Core idea

A **locally ringed space** is a topological space equipped with a sheaf of rings such that every stalk is a local ring. This locality condition is what makes schemes behave like geometric spaces with a well-defined notion of functions near each point.

A **scheme** is a locally ringed space that is locally isomorphic to an affine scheme. In other words, every point has an open neighborhood that looks like \(\mathrm{Spec}(A)\) for some ring \(A\).

## Affine schemes

The basic building block is the spectrum of a ring:

- **Points** are prime ideals of the ring.
- The **Zariski topology** is defined by closed sets of the form \(V(I)\).
- The **structure sheaf** assigns rings of regular functions to open sets.
- The stalk at a prime ideal \(\mathfrak p\) is the local ring \(A_{\mathfrak p}\).

This construction makes \(\mathrm{Spec}(A)\) into a locally ringed space, and ring homomorphisms \(A \to B\) induce morphisms of schemes in the opposite direction.

## Why local rings matter

The condition that stalks are local rings is essential:

- it identifies a unique maximal ideal at each point,
- it allows one to talk about functions defined “near a point,”
- and it ensures that morphisms of schemes behave correctly on local data.

Hartshorne emphasizes that omitting the local-ring condition would break the basic duality between rings and affine schemes.

## Glueing local pieces

Schemes are not limited to affine objects. One can glue affine schemes along open subschemes to build more complicated spaces.

This is the scheme-theoretic analogue of constructing manifolds from coordinate charts, but with algebraic charts instead of smooth ones. The result is that many geometric objects can be assembled from affine pieces while preserving a ringed-space structure.

## Relation to varieties

Classical varieties over an algebraically closed field embed naturally into the language of schemes:

- a variety gives a scheme whose closed points recover the original variety,
- the structure sheaf matches the regular functions on open sets,
- and the resulting functor from varieties to schemes is fully faithful.

This is one of the main conceptual transitions in the book, and it prepares the ground for later developments in [[concepts/divisors-and-line-bundles]] and [[concepts/cohomology-in-algebraic-geometry]].

## Key properties

Important features of schemes and locally ringed spaces include:

- **locality**: properties can often be checked on affine open sets,
- **functoriality**: morphisms come from ring maps on affine charts,
- **glueing**: schemes are assembled from compatible local data,
- **generalization**: schemes include classical varieties, nonreduced spaces, and arithmetic objects such as \(\mathrm{Spec}(\mathbb Z)\).

## In Hartshorne’s book

The chapter on schemes develops this framework systematically:

- first introducing sheaves,
- then affine schemes and \(\mathrm{Proj}\),
- then properties such as separatedness, properness, flatness, and smoothness,
- and finally using schemes as the language for divisors, cohomology, and families.

This framework is foundational for the rest of the book and is one of the main themes of [[summaries/01_英文数学_Algebraic Geometry (Robin Hartshorne)]].

## Related concepts

- [[concepts/schemes]]
- [[concepts/cohomology-in-algebraic-geometry]]
- [[concepts/divisors-and-line-bundles]]