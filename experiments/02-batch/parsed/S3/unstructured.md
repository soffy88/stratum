1 2 0 2

## l u J

5 1

] P A . h t a m

[

1 v 0 2 3 7 0 . 7 0 1 2 : v i X r a

## Biharmonic nonlinear scalar ﬁeld equations

## Jarosław Mederski and Jakub Siemianowski

ABSTRACT. We prove a Brezis-Kato-type regularity result for weak solutions to the biharmonic nonlinear equation

∆2u = g(x,u)

## in RN

with a Carathéodory function g : RN × R → R, N ≥ 5. The regularity results give rise to the existence of ground state solutions provided that g has a general subcritical growth at inﬁnity. We also conceive a new biharmonic logarithmic Sobolev inequality

## ZRN

## |u|2 log |u|dx ≤

## N 8

## log

(cid:18)

## C

## ZRN

|∆u|2 dx

(cid:19)

,

for u ∈ H2(RN),

## ZRN

u2 dx = 1,

## for a constant 0 < C <

(cid:16)

## 2 πeN

(cid:17)

2

and we characterize its minimizers.

- 1. Introduction
The study of higher-order differential elliptic operators is important, e.g. in nonlinear elasticity [3], low Reynolds number hydrodynamics, in structural engineering [21,24] as well as in nonlinear optics [11], and has attracted attention from the mathematical point of view [12]. The methods developed for the second order problem, e.g. involving the Laplacian −∆, may no longer be available. For instance, it is the well- known that the bi-Laplacian (−∆)2 = ∆2 cannot be studied by means of some classical methods such as maximum principles, Polya-Szeg˝o inequalities, or even if (∆u)2 ∈ L1(RN), then it is possible that ∆|u| /∈ L1

## loc(RN).

The ﬁrst aim is of this work is to establish a regularity result in the spirit of Brezis-Kato [6] of weak

## solutions to

∆2u = g(x,u),

(1.1) where Ω ⊂ RN is a domain, N ≥ 2 and g : Ω×R → R is a Carathéodory function. If we suppose that Ω is bounded, then there is an extensive literature devoted to this problem. Namely, recall that if g(x,u) = f(x), then Agmon, Douglis, Nirenberg [2] showed that for 1 < q < ∞, f ∈ Lq(Ω), there exists a unique strong solution u ∈ W 2,2 (Ω)∩W 4,q(Ω) to (1.1) provided that ∂Ω ∈ C4 see also [12, Corollary 2.21] and references therein. Recently Mayboroda and Maz’ya [17] showed L∞-estimates of u (resp. ∇u), where f ∈ C∞ 0 (Ω), Ω is an arbitrary bounded domain and N = 4,5 (resp. N = 2,3). To the best of our knowledge, a variant of Brezis-Kato result [6] for (1.1) is known only on a bounded domain in a particular case. Namely, Van der Vorst [25] showed that, if N ≥ 5, g(x,u) = a(x)u and a(x) ∈ LN/4(Ω), then any weak solution u ∈ W 1,2 (Ω) ∩ W 2,2(Ω) to (1.1) satisﬁes u ∈ Lq(Ω) for all 1 ≤ q < ∞. This result is suitable to show the regularity for the biharmonic equation with the nonlinearities of the special form g(x,u) = f(u)u cf. [25, Lemma B3]. In this paper we give a full answer to the problem on an arbitrary domain and for general g with the adequate Brezis-Kato growth as we shall see below.

x ∈ Ω,

0

0

2000 Mathematics Subject Classiﬁcation. 35J91,35J20. Key words and phrases. Nonlinear scalar ﬁeld equation, Brezis-Kato reqularity, biharmonic logarithmic Sobolev inequality,

## critical point theory, Pohozaev manifold.

1

2

## J. MEDERSKI AND J. SIEMIANOWSKI

From now on we assume that Ω ⊂ RN possibly unbounded domain and N ≥ 5. Inspired by [6], we

impose on g the following growth assumption:

(1.2)

|g(x,s)| ≤ a(x)

1 + |s|

,

for s ∈ R and a.e. x ∈ Ω, where 0 ≤ a ∈ LN/4

## loc (Ω).

The ﬁrst main result reads as follows. THEOREM 1.1. Let u ∈ W 2,2

(cid:0)

(cid:1)

loc (Ω) be a weak solution to (1.1), where g satisﬁes (1.2). Then u ∈

loc (Ω) ∩ W 4,q C3,α

loc (Ω), for any 0 < α < 1 and 1 ≤ q < ∞.

It is worth mentioning that in proof of Theorem 1.1 we can no longer apply classical techniques for Laplacian, e.g. due to Brezis and Kato [6], or Brezis and Lieb [7, Theorem 2.3], since ∆|u| may not be well-deﬁned for u ∈ W 2,2 loc (Ω). Moreover, the Moser iteration technique does not seem to be applicable straightforwardly for g.

We shall present some consequences of Theorem 1.1 in Ω = RN. Let us deﬁne D2,2(RN) as a comple- 2. By the use of 0 (RN),

1

## 0 (RN) with respect to the norm kukD2,2 :=

tion of the space C∞ the Fourier transform and the Plancharel theorem we ﬁnd a constant c > 0 such that, for u ∈ C∞

|α|=2 k∂αuk2

L2(RN)

(cid:16)P

(cid:17)

## 1 c

kukD2,2(RN) ≤ k∆ukL2(RN) ≤ ckukD2,2(RN). Therefore, the norms kuk := k∆ukL2(RN) and kukD2,2(RN) are equivalent on D2,2(RN). Moreover, D2,2(RN) is a Hilbert space with the inner product

## hu,vi :=

## ∆u∆v dx

## for u, v ∈ D2,2(RN)

## RN

## Z

and u ∈ D2,2(RN) is a weak solution to (1.1) provided that

0 (RN).

## for any v ∈ C∞

## hu,vi =

## g(x,u)v

## RN

## Z

As usually expected, the following general Pohožaev-type result holds, cf. [23]. THEOREM 1.2. Let u ∈ D2,2(RN) be a weak solution to (1.1), where g satisﬁes (1.2). Then

2 N − 4 provided that G(x,u), x · ∂xG(x,u) ∈ L1(RN), where G(x,s) :=

2N N − 4

|∆u|2 dx =

(1.3)

## G(x,u)dx +

## RN

## RN

## Z

## Z

## x · ∂xG(x,u)dx.

RN Z s 0 g(x,t)dt, x ∈ RN, t ∈ R.

We demonstrate that the Brezis-Kato result for biharmonic Laplacean as well as Theorem 1.2 open the way to study the existence of solutions and their regularity for (1.1). Indeed, let us assume that g is independent of x and the following condition holds:

## R

1 + |s|2∗∗−1 N−4. Then a(x) := g(u(x))/(1 + |u(x)|) ∈ LN/4 where 2∗∗ := 2N (cid:1) of Theorem 1.1, weak solutions to the semilinear problem (1.1) belong to C3,α introduce the energy functional

for s ∈ R,

(g0) there is a constant c > 0 such that |g(s)| ≤ c

## loc (RN) for u ∈ L2∗∗

## (RN) and in view loc (RN). We

(cid:0)

loc (RN) ∩ W 4,q

1 2

|∆u|2 −

(1.4)

J(u) :=

G(u)dx,

## RN

RN s 0 g(t)dt. Next, we show the existence of weak solutions to (1.1) under growth assumption where G(s) = at 0 and at inﬁnity inspired by a seminal paper due to Berestycki and Lions [5] (cf. [19,20]). We assume that g is continuous, g(0) = 0 and (g0) holds. Let

## Z

## Z

## R

G+(s) :=

## (R R

s 0 max{g(t),0}dt 0 s max{−g(t),0}dt

for s ≥ 0, for s < 0,

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

and g+(s) = G′

+(s). Suppose in addition, that and the following conditions are satisﬁed:

(g1) lims→0 G+(s)/|s|2∗∗ (g2) there exists ξ0 > 0 such that G(ξ0) > 0, (g3) lim|s|→∞ G+(s)/|s|2∗∗ = 0. We introduce the Pohožaev manifold

= 0,

(1.5)

M :=

u ∈ D2,2(RN) \ {0} :

|∆u|2 = 2∗∗

## G(u)dx

,

## RN

## RN

## Z

## Z

## o

## n

and in view of Theorem 1.2, M contains all nontrivial solutions. The existence result reads as follows.

THEOREM 1.3. Let (g0)–(g3) be satisﬁed. Then infM J > 0 and there is a ground state solution u0 ∈ loc (RN),

D2,2(RN) to (1.1), i.e. u0 ∈ M solves (1.1) and J(u0) = infM J. Moreover u0 ∈ C3,α for any 0 < α < 1 and 1 ≤ q < ∞.

loc (RN)∩W 4,q

Theorem 1.3 enables us to consider the following nonlinearity

(1.6)

## G(s) = s2 log|s|

for s 6= 0, and G(0) = 0

which satisﬁes (g0)–(g3). In view of Theorem 1.3 there is a ground state solution to (1.1) and

CN,log := 2∗∗

1 2

−

1 2∗∗

− 4

## N−4(inf M

J)

4 N−4.

(cid:16)

(cid:17)

We gain the following new biharmonic logarithmic Sobolev inequality.

## THEOREM 1.4. For any u ∈ D2,2(RN) such that

RN |u|2 dx = 1, there holds

(1.7)

## N 8

## log

(cid:18)

## 8e CN,log(N − 4)

(cid:19)

(N−4)/N

## R

## RN

## Z

|∆u|2 dx

!

≥

## Z

## RN

## |u|2 log |u|dx

## and

(N−4)/N

## 8e CN,log(N − 4)

## 2 πeN

2

.

<

(cid:18)

(cid:19)

(cid:17)

(cid:16)

Moreover the equality in (1.7) holds provided that u = u0/ku0kL2(RN) and u0 is a ground state solution to (1.1). If the equality in (1.7) holds for u, then there are uniquely determined λ > 0 and r > 0 such that u0 := λu(r·) ∈ M and u0 is a ground state solution to (1.1).

Recall that the classical logarithmic Sobolev inequality given in [26]:

## N 4

## 2 πeN

|u|2 log(|u|)dx,

|∇u|2 dx

for u ∈ H1(RN),

|u|2 dx = 1,

## log

≥

(1.8)

## RN

## RN

## RN

## Z

## Z

## Z

(cid:16)

(cid:17)

which is equivalent to the Gross inequality [13], cf. [14]. Recall that the optimality of (1.8) and the char- acterization of minimizers have been already proved by Carlen [8] in the context of the Gross inequality as well as by del Pino and Dolbeault [9,10] for the interpolated Gagliardo–Nirenberg inequalities and the Lp- Sobolev logarithmic inequality. A generalization of the optimal Gross inequality in Orlicz spaces is given by Adams [1]. However, to the best of our knowledge, the logarithmic Sobolev inequality for higher order operators have not been obtained in the literature so far and (1.8) seems to be the ﬁrst one for the biharmonic Laplacian. Note that, in contrast to (1.8) and the Laplacian problem involving (1.6), we do not know ground state solutions to (1.1) explicitly. Hence the exact computation of CN,log remains an open question.

The paper is organized as follows. In Section 2 we prove Theorem 1.1 and in Section 3 we obtain the Pohožaev-type result. The main result of Section 4 is a general variant of Lion’s lemma (Lemma 4.1) in D2,2(RN), which is crucial for the proof of Theroem 1.3 given in Section 5. The last Section 6 is devoted to the biharmonic logarithmic Sobolev inequality.

3

4

## J. MEDERSKI AND J. SIEMIANOWSKI

- 2. Regularity theory and proof of Theorem 1.1
Let N, k ∈ N and 1 ≤ p < ∞ with N > kp. We deﬁne Dk,p(RN) as a completion of the space

## 0 (RN) with respect to the norm C∞

## 1 p

## Hence

## kukDk,p :=





## X|α|=k

## kDαukp

## Lp(RN)



,

## u ∈ C∞

0 (RN).

(2.1)

## Dk,p(RN) ⊂ Dk−l, Np

N−lp(RN),

0 ≤ l ≤ k,

## and

## k

(2.2)

## Xj=0 X|α|=k−j

## kDαuk L

## Np N−jp (RN)

≤ ckukDk,p,

## u ∈ Dk,p(RN).

We ﬁx an open set Ω ⊂ RN. We recall that by the standard approach based on molliﬁers and the Calderon–Zygmund Lp–estimates for higher order elliptic operators [22, (2.6)] we have the following lemma.

LEMMA 2.1. Let 1 < p < ∞ and k be a positive integer. If w ∈ Lp

## loc(Ω) and ∆kw ∈ Lp

## loc(Ω), then

## w ∈ W 2k,p

## loc (Ω).

loc (Ω) is a weak solution to (1.1), where g satisﬁes (1.2). Clearly u ∈ L2∗∗ 4 and 2N

## Suppose that u ∈ W 2,2 N+4 < N

## U ⊂⊂ Ω. Since 2N

N+4 = 2∗∗ N−4

## N+4, by the Hölder inequality

## loc (Ω). Fix

|g(x,u)|

## 2N N+4 dx ≤ c

|a(x)|

2N N+4 + |a(x)|

## N 4

N+4|u|2∗∗ N−4

8

N+4 dx < ∞,

## ZU

## ZU

for some constant c > 0. Then, by the distributional equality

∆2u = g(x,u) ∈ L

## 2N N+4 loc

(Ω),

and Lemma 2.1, we infer that u ∈ W

## 4, 2N N+4 loc

(Ω).

Now the crucial step is the following lemma.

N+4 and u ∈ W 4,p LNp/N−5p loc Lq loc(Ω) for every 1 ≤ q < ∞, PROOF. If 4p ≥ N, then the conclusion follows immediately by the Sobolev embedding W 4,p

## LEMMA 2.2. Let p ≥ 2N

loc (Ω) be a weak solution to (1.1), where g satisﬁes (1.2). Then

(Ω),

## if 5p < N, if 5p ≥ N.

## u ∈

(

## loc (Ω) ⊂

## Lq

loc(Ω), q ≥ 1. Thus, we can clearly assume that 4p < N. Let us deﬁne

˜a(x) :=

g(x,u(x))

u(x) χ{x∈Ω||u(x)|>1}(x),

0 (

for u(x) 6= 0, for u(x) = 0,

b(x) := g(x,u(x))χ{x∈Ω||u(x)|≤1}(x),

and observe that g(x,u) = ˜a(x)u + b(x) and ˜a,b ∈ LN/4

## loc (Ω).

Let U be an arbitrary open bounded subset of Ω such that U ⊂ U ⊂ Ω. We ﬁnd an open bounded V with C∞-smooth boundary such that U ⊂ V ⊂ V ⊂ Ω. Indeed, let ξ ∈ C∞ 0 (Ω) be a smooth cut-off function such that ξ ≡ 1 on U and 0 ≤ ξ ≤ 1. By Sard’s theorem, there is a regular value c ∈ (0,1). Then V = ξ−1((c,1]) is an open bounded subset with the smooth boundary ∂V = ξ−1({c}) satisfying U ⊂ V ⊂ V ⊂ Ω.

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

Now take η ∈ C∞

0 (V ) such that η = 1 on U and 0 ≤ η ≤ 1. We restrict our problem to V . By the

assumption u ∈ W 4,p(V ) is a distributional solution of

(2.3)

∆2u = ˜a(x)u + b(x)

## in V

and ˜a,b ∈ LN/4(V ). We deﬁne

v := uη. Certainly, we have v ∈ W 4,p(V ) ⊂ H2(V ) and v ∈ H1 yield

## 0(V ), since suppη ⊂⊂ V . Standard calculations

∆2v = (∆2u)η + 4∇∆u · ∇η + 4

∇uxi · ∇ηxi + 2∆u∆η + 4∇u · ∇∆η + u∆2η

(2.4)

## Xi=1N

=:K(u)

=: (∆2u)η + K(u). Observe that u ∈ W 4,p(V ) ⊂ W 3,p∗

|

## {z N−p and η ∈ C∞

(V ), p∗ = Np

0 (V ) imply that

}

(2.5)

## kK(u)kLp

∗

(V ) ≤ ckukW 3,p

∗

(V )kηkW 4,∞(V ) ≤ c(η)kukW 4,p(V ),

for some constant c(η) > 0.

In view of [25, Lemma B.2], for every ε > 0 there are qε ∈ LN/4(V ) and

## fε ∈ L∞(V ) such that

(2.6)

## ˜a(x)v = qε(x)v +

fε,

## b

## and

(2.7)

b kqεkLN/4(V ) ≤ ε.

By (2.4), (2.3) and (2.6) we get

∆2v = (∆2u)η + K(u)

(2.8)

= ˜a(x)v + b(x)η + K(u) = qε(x)v + fε + K(u),

## where

(2.9)

## fε :=

fε + b(x)η ∈ L

N 4 (V ).

We recall some needed regularity results from [2] (see also [12, Thm 2.20]), for all 1 < q < ∞,

## b

¯g ∈ Lq(V ), there exists a unique strong solution u ∈ W 4,q(V ) to the problem

(

(−∆)2u = ¯g u = ∆u = 0

## in V, on ∂V.

satisfying

kukW 4,q(V ) ≤ cqk¯gkLq(V ), where cq > 0 depends only on N, q and V . Denote by Tq the linear operator g 7→ u considered as an operator from Lq(V ) to W 4,q(V ) and rewrite the above inequality as

(2.10)

kTq¯gkW 4,q(V ) ≤ cqk¯gkLq(V ). Obviously, Tq is the Lq-inverse of the bilaplacian (−∆)2 considered with the Navier boundary conditions u = ∆u = 0 on ∂V .

Now we can rephrase (2.8) in the language of operators

(2.11)

v − Aε,qv = hε,q,

## where Aε,qv := Tq(qεv) and hε,q := Tq(fε + K(u)).

We consider two cases separately.

5

6

## J. MEDERSKI AND J. SIEMIANOWSKI

## Case I: 5p < N.

In what follows we take q = p∗. By the Sobolev embedding W 4,p∗

(V ) ⊂ L

Np N−5p(V ), (2.10), (2.9) and

(2.5), we have

## khε,p∗k L

## Np N−5p (V )

## ≤ cSobolevkTp∗(fε + K(u))kW 4,p

∗

(V )

## ≤ cSobolevcp∗kfε + K(u)kLp

∗

(V )

(2.12)

≤ c

≤ c

(cid:18)

(cid:18)

## kfεk L

## kfεk L

N 4 (V )

N 4 (V )

## + kK(u)kLp

∗

(V )

(cid:19) + c(η)kukW 4,p(V )

(cid:19)

,

where c > 0 is some constant. We estimate the norm of the linear operator Aε,p∗ : L applying the Sobolev embedding W 4,p∗

Np N−5p(V ) and (2.10)

(V ) ⊂ L

## Np N−5p(V ) → L

## Np N−5p(V )

(2.13)

## kAε,p∗vk L

## Np N−5p (V )

≤ cSobolevkTp∗(qεv)kW 4,p

∗

## (V ) ≤ cSobolevcp∗kqεvkLp

∗

(V ).

We use the Hölder inequality with the exponents

1 N 4

+

## 1 Np N−5p

=

1 p∗

to obtain

(2.14)

## kqεvkLp

∗

## (V ) ≤ kqεkLN/4(V )kvk L

## Np N−5p (V )

.

In view of (2.13), (2.14) and (2.7) we gain

## kAε,p∗vk L

## Np N−5p (V )

## ≤ cSobolevcp∗εkvk L

## Np N−5p (V )

.

We choose ε := (2cSobolevcp∗)−1 to deduce

(2.15)

## kAε,p∗k L

## Np N−5p →L

## Np N−5p

≤

1 2

.

Then (I − Aε,p∗) is invertible on the space L

Np N−5p(V ) with the norm bounded by 2 and by (2.11)

(2.16)

v = (I − Aε,p∗)−1hε,p∗,

## so by the above and by (2.12)

## kvk

## L

## Np N−5p (V )

(I − Aε,p∗)−1

≤

## Np N−5p

## Np N−5p →L

L kfεkL∞(V ) + c(η)kukW 4,p(V )

(cid:13) (cid:13) ≤ 2c (cid:13)

(cid:13) (cid:13) (cid:13)

## khε,p∗k L < ∞.

## Np N−5p (V )

(cid:1)

(cid:0)

Np N−5p(V ) and, since u = v on U ⊂ Ω and U is arbitrary, we ﬁnally get u ∈ L

Hence v ∈ L claimed. This ﬁnishes the proof of Case I.

## Np N−5p loc

## (Ω) as

## Case II: 5p ≥ N.

We proceed similarly as in Case I. Fix any Np

## N−4p ≤ q < ∞ and deﬁne r := Nq

N+4q. Then we have N−p. We employ the Sobolev embedding W 4,r(V ) ⊂ Lq(V ), (2.10), (2.9) and (2.5) to

## 4 ≤ Np

1 < r < N

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

## estimate

khε,rkLq(V ) ≤ cSobolevkTr(fε + K(u))kW 4,r(V )

## ≤ cSobolevcrkfε + K(u)kLr(V )

(2.17)

≤ c

(cid:18)

## kfεk L

N 4 (V )

## + kK(u)kLp

∗

(cid:19)

≤ c

## kfεk L

,

+ c(η)kukW 4,p(V )

N 4 (V )

(cid:18)

(cid:19)

for some constant c > 0. We bound the norm of Aε,r : Lq(V ) → Lq(V ) by exploiting the Sobolev embedding W 4,r(V ) ⊂ Lq(V ) and (2.10)

(2.18)

kAε,rkLq(V ) ≤ cSobolevkTr(qεv)kW 4,r(V ) ≤ cSobolevcrkqεvkLr(V ).

We use Hölder’s inequality with exponents

1 N 4

+

## 1 Nr N−4r

=

## 1 r

and (2.7) to obtain

= 1 q | {z }

(2.19)

kqεvkLr(V ) ≤ kqεk L

N 4 (V )

kvkLq(V ) ≤ εkvkLq(V ).

We choose ε = (2cSobolevcr)−1 and from (2.18), (2.19) deduce that

## kAε,rkLq→Lq ≤

1 2

.

As in the last part of Case I, we then show that v ∈ Lq(V ). This implies that u ∈ Lq(U) and, since U ⊂ Ω (cid:3) and q ≥ Np

N−4p were arbitrary, the proof of Case II is completed.

4, 2N N+4 loc loc(Ω), for every q ≥ 1. If N = 5 or N = 6, then, by Lemma 2.2, u ∈ Lq

Proof of Theorem 1.1. Let u ∈ W 2,2 that u ∈ Lq q ≥ 1, and we are done. If N > 6, then we deﬁne p1 := 2N

loc (Ω) be a weak solution to (1.1). Then u ∈ W

(Ω). We show loc(Ω), for every N+4, 5p1 < N, and we use Lemma 2.2 to obtain

## u ∈ L

## Np1 N−5p1 loc

## (Ω). Since Np1 N−5p1

= 2N

N−6,

p1 < p2 :=

## Np1 N − 5p1

N − 6 N + 2

=

2N N + 2

<

## N 4

.

Fix U ⊂⊂ Ω. Observe that p2

N+2

8 = N

## 4 and by the Hölder inequality

## |g(x,u)|p2 dx ≤ c

|a(x)|p2 dx + c

|a(x)|p2

N+2

## 8 dx

8 N+2

|u|

## Np1 N−5p1 dx

N−6 N+2 < ∞

## ZU

## ZU

## (cid:16)ZU loc(Ω). Since u ∈ W 4,p1

## (cid:16)ZU

(cid:17)

(cid:17) loc (Ω) ⊂ Lp2

for some constant c > 0. Therefore we get ∆2u = g(x,u) ∈ Lp2 use Lemma 2.1 to get u ∈ W 4,p2 applying Lemma 2.2 in this fashion and get a ﬁnite sequence (pk)K

loc(Ω), we 2 . We continue

loc (RN). Let K be the largest natural number less than N−4

## k=1 such that for k = 1,...,K

## pk :=

2N N + 6 − 2k

,

## pk

N + 6 − 2k 8

=

## N 4

,

pk+1 =

## Npk N − 5pk

N − 4 − 2k N + 4 − 2k

,

if k ≥ 1.

7

8

## J. MEDERSKI AND J. SIEMIANOWSKI

NpK N−5pK By the deﬁnition of K, we get 5pK < N, NpK loc N−5pK obtain that u ∈ Lq loc(Ω), for every q ≥ 1. Since ∆2u = g(x,u) ∈ Lq loc (Ω), q ≥ 1, so by the Sobolev embedding u ∈ C3,α Lemma 2.1, u ∈ W 4,q

## ≥ N and u ∈ L

(Ω). Finally, by Lemma 2.2 we loc(Ω), for every 1 ≤ q < ∞, by (cid:3)

loc (Ω), for every 0 < α < 1.

- 3. Pohožaev identity Proof of Theorem 1.2. One can ﬁnd ϕ ∈ C∞(R) satisfying ϕ|(−∞,1] ≡ 1, ϕ|[2,∞) ≡ 0 and 0 ≤ ϕ ≤ 1. For every n ≥ 1, we deﬁne ϕn ∈ C∞ By Theorem 1.1, we may assume that u ∈ C3,α
0 = ∆2u − g(x,u)

## a.e. in RN.

Thus, for a.e. x ∈ RN and for every n, we obtain

(3.1)

0 = (∆2u − g(x,u))ϕnx · ∇u.

The following identities hold

g(x,u)ϕnx · ∇u = div(ϕnG(x,u)x) − G(x,u)x · ∇ϕn − NϕnG(x,u) − ϕnx · ∂xG(x,u)

## and

∆2uϕnx · ∇u = div(ϕn(x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − ϕn∇(x · ∇u) · ∇(∆u).

We transform the rightmost term of the above equation

ϕn∇(x · ∇u) · ∇(∆u) = −ϕn∆u∆(x · ∇u) + ϕndiv(∆u∇(x · ∇u))

= −ϕn∆u(2∆u + x · ∇∆u) + div(ϕn∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u) = −2ϕn(∆u)2 − ϕn∆ux · ∇∆u + div(ϕn∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u).

Finally, we rewrite the second term of the above line as follows

## ϕn∆ux · ∇∆u = div

(cid:18)

## ϕn

(∆u)2 2

## x

(cid:19)

−

1 2

(∆u)2∇ϕn · x −

## N 2

ϕn(∆u)2.

Putting the above identities into (3.1) we get

0 = −div(ϕnG(x,u)x) + G(x,u)x · ∇ϕn + NϕnG(x,u) + ϕnx · ∂xG(x,u)

+ div (ϕn(x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − div

N − 4 2 or, equivalently,

−

ϕn(∆u)2 −

1 2

(cid:18)

(∆u)2x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u)

## ϕn

(cid:18)

∆u∇(x · ∇u) −

(∆u)2 2

## x

(cid:19)(cid:19)

(3.2) div

(cid:18)

(∆u)2 2

## ϕn

## x

G(x,u)x + ∆u∇(x · ∇u) − x · ∇u∇∆u −

(cid:19)(cid:19)

(cid:18)

= G(x,u)x · ∇ϕn + NϕnG(x,u) + ϕnx · ∂xG(x,u) − (x · ∇u)(∇ϕn · ∇∆u)

−

N − 4 2

ϕn(∆u)2 −

1 2

(∆u)2x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u).

Fix n ≥ 1 and take R > 0 such that suppϕn ⊂ BR. By the divergence theorem, we obtain

0 =

G(x,u)x · ∇ϕn + NϕnG(x,u) + ϕnx · ∂xG(x,u) − (x · ∇u)(∇ϕn · ∇∆u)

ZBR −

N − 4 2

(∆u)2ϕn −

1 2

(∆u)2x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u)dx.

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

## Note that

−

(x·∇u)(∇ϕn·∇∆u)dx =

∆u∇ϕn·∇(x·∇u)+∆u∆ϕnx·∇udx−

## div (x · ∇u∆u∇ϕn)

## ZBR

## ZBR

## ZBR

=0

Summing up, we have (3.3)

|

## {z

0 =

G(u)x · ∇ϕn + NϕnG(x,u) + ϕnx · ∂xG(x,u) + 2∆u∇ϕn · ∇(x · ∇u) + ∆u∆ϕnx · ∇u

## ZBR

−

N − 4 2

(∆u)2ϕn −

1 2

## (∆u)2x · ∇ϕn dx

=

G(u)x · ∇ϕn + NϕnG(x,u) + ϕnx · ∂xG(x,u) + 2∆u∇ϕn · ∇(x · ∇u) + ∆u∆ϕnx · ∇u

## Z

## RN

−

N − 4 2

(∆u)2ϕn −

1 2

(∆u)2x · ∇ϕn dx.

We return to (3.3) and pass to the limit as n → ∞ to obtain

N − 4 2

|∆u|2 dx,

0 = N

## G(x,u)dx +

## x · ∂xG(x,u)dx −

## RN

## RN

## RN

## Z

## Z

## Z

where we used Lebesgue’s dominated convergence theorem and the properties of ϕn. The proof is com- (cid:3) pleted.

- 4. Lions lemma
We prove a biharmonic variant of Lion’s lemma, cf. [15,16], [20, Section 2]. LEMMA 4.1. Suppose that (un) is bounded in D2,2(RN) and for some r > 0

(4.1)

## lim n→∞

## sup y∈RN ZB(y,r)

|un|2 dx = 0.

## Then

## Z

for every continuous Ψ : R → R satisfying

## RN

## Ψ(un)dx → 0

## as n → ∞

Ψ(s) |s|2∗∗ = lim We prove the following result, which implies the variant of Lions’s lemma in D2,2(RN). LEMMA 4.2. Suppose that (un) ⊂ D2,2(RN) is bounded. Then un(· + yn) ⇀ 0 in D2,2(RN) for any

Ψ(s) |s|2∗∗ = 0.

## lim s→0

(4.2)

|s|→∞

(yn) ⊂ ZN if and only if

## Ψ(un)dx → 0

## RN

## Z

## for any continuous Ψ : R → R satisfying (4.2).

## as n → ∞

PROOF. Let (un) be a sequence in D2,2(RN) be such that un(· + yn) ⇀ 0 in D2,2(RN) for every (yn) ⊂ ZN. Take any ε > 0 and 2∗ < p < 2∗∗ and suppose that Ψ satisﬁes (4.2). Then we ﬁnd 0 < δ < M and c(ε) > 0 such that

Ψ(s) ≤ ε|s|2∗∗ Ψ(s) ≤ ε|s|2∗∗ Ψ(s) ≤ c(ε)|s|p

for |s| ≤ δ,

## for |s| > M, for |s| ∈ (δ,M].

}

9

## dx.

10

## J. MEDERSKI AND J. SIEMIANOWSKI

Let us deﬁne (wn) by

|un(x)| |un(x)|2∗∗/2∗ We are about to show that (wn) is bounded in W 1,2∗ δ2∗−2∗∗ |wn(x)|2∗

for |un(x)| > δ, δ1−2∗∗/2∗ for |un(x)| ≤ δ. (RN). First of all, we have |un|2∗∗

wn(x) :=

(

|un|2∗

## dx =

## dx

## dx +

## RN

Z{|un|≥δ}

Z{|un|≤δ} = δ2∗−2∗∗

## Z

|un|2∗∗ |un|2∗∗−2∗ dx |un|2∗∗ δ2∗∗−2∗ dx

|un|2∗∗

## dx +

Z{|un|≤δ}

Z{|un|>δ}

(4.3)

≤ δ2∗−2∗∗

|un|2∗∗

## dx +

Z{|un|≤δ}

Z{|un|>δ}

= δ2∗−2∗∗

|un|2∗∗

## dx.

## RN

## Z

By the absolute continuous characterization (see §1.1.3 in [18]), we infer that each un is absolutely contin- uous on almost every line parallel to the 0xi-axis, for i = 1,...,N. Thus the same holds for each wn, since wn = F(un), where F(t) = min{δ1−2∗∗/2∗ ,|t|} is a globally Lipschitz function. Moreover, for every i = 1,...,N, we have

|t|2∗∗/2∗

## ∂wn ∂xi

=

(

2∗∗ 2∗ δ1−2∗∗/2∗ sign(un)∂un ∂xi

sign(un)|un|2∗∗/2∗−1 ∂un ∂xi ,

,

for |un(x)| ≤ δ, for |un(x)| > δ.

## Thus

2∗

2∗

2∗

2∗∗ 2∗

∂wn ∂xi (cid:12) (cid:12) (cid:12) (cid:12)

∂un ∂xi (cid:12) (cid:12) (cid:12) (cid:12) (cid:12) (cid:12) (cid:12) (cid:12) Z{|un|>δ} (cid:12) (cid:12) (cid:12) (cid:12)

∂un ∂xi (cid:12) (cid:12) (cid:12) (cid:12)

δ2∗−2∗∗

|un|2∗∗−2∗

## dx +

## dx =

RN (cid:12) Z (cid:12) (cid:12) (cid:12)

Z{|un|≤δ} 2∗ ∂un ∂xi (cid:12) (cid:12) 2∗ (cid:12) (cid:12) dx.

Z{|un|>δ} (cid:12) (cid:12) (cid:12) (cid:12)

(cid:19)

(cid:18)

2∗

2∗

2∗∗ 2∗

∂un ∂xi (cid:12) (cid:12) (cid:12) (cid:12)

(4.4)

≤

## dx

## dx +

Z{|un|≤δ} (cid:12) (cid:12) (cid:12) ∂un (cid:12) ∂xi (cid:12) (cid:12) (cid:12) (cid:12)

(cid:19)

(cid:18)

2∗

2∗∗ 2∗

≤

RN (cid:12) Z (cid:12) By (4.3), (4.4) (again using an absolute continuous characterization on lines from §1.1.3 [18]) and the fact (cid:12) that (un) is bounded in D2,2(RN), we conclude that (wn) is bounded in W 1,2∗ (cid:12)

(cid:18)

(cid:19)

(RN).

2∗

## dx

Let Ω = (0,1)N and y ∈ RN be arbitrary. Then, by the Sobolev inequality one has

## Ψ(un)dx =

## Ψ(un)dx +

## Ψ(un)dx

## ZΩ+y

Z(Ω+y)∩{δ<|un|≤M}

Z(Ω+y)∩({|un|>M}∪{|un|≤δ})

≤ c(ε)

## |wn|p dx + ε

|un|2∗∗

## dx

Z(Ω+y)∩{δ<|un|≤M}

## ≤ c(ε)C

|wn|2∗

+ |∇wn|2∗

## dx

Z(Ω+y)∩({|un|>M}∪{|un|≤δ}) + ε

1−2∗/p

## |wn|p dx

|un|2∗∗

dx,

## (cid:16)ZΩ+y

(cid:17)(cid:16)ZΩ+y

## ZΩ+y

(cid:17)

where C > 0 is a constant from the Sobolev inequality. Then we sum the inequalities over y ∈ ZN and get

1−2∗/p

## Ψ(un)dx ≤ c(ε)C

## RN

## RN

Z Let us take (yn) ⊂ ZN such that

(cid:18)Z

|wn|2∗

+ |∇wn|2∗

## dx

(cid:19)

## sup y∈ZN ZΩ

|wn(· + y)|p dx

!

## + ε

## Z

## RN

|un|2∗∗

## sup y∈ZN

## ZΩ

|wn(· + y)|p dx ≤ 2

## ZΩ

|wn(· + yn)|p dx

## dx.

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

for any n ≥ 1. By the assumption un(· + yn) ⇀ 0 in D2,2(RN) and passing to a subsequence we obtain un(· + yn) → 0 in Lp(Ω).

Since |wn(x)| ≤ |un(x)|, we infer that wn(· + yn) → 0 in Lp(Ω). Therefore

limsup n→∞ Z

## RN

## Ψ(un)dx ≤ εlimsup

## n→∞ Z

## RN

|un|2∗∗

dx,

and since ε > 0 is arbitrary, the assertion follows.

On the other hand, suppose that un(· + yn) does not converge to 0 in D2,2(RN), for some (yn) in ZN, and Ψ(un) → 0 in L1(RN). We may assume that un(·+yn) → u0 6= 0 in Lp(Ω) for some bounded domain Ω ⊂ RN and 1 < p < 2∗∗. Take any ε > 0, q > 2∗∗ and let us deﬁne Ψ(s) := min{|s|p,εp−q|s|q} for s ∈ R. Then

## Z

## RN

## Ψ(un)dx ≥

## ZΩ+yn∩{|un|≥ε}

## |un|p dx +

## ZΩ+yn∩{|un|≤ε}

## εq−p|un|q dx

=

## |un|p dx +

## εp−q|un|q − |un|p dx

## ZΩ+yn

## ZΩ+yn∩{|un|≤ε}

≥

## |un|p dx − εp|Ω|.

## ZΩ+yn

Thus we get un(· + yn) → 0 in Lp(Ω) and this contradicts u0 6= 0.

Proof of Lemma 4.1. Suppose that there is (yn) ⊂ ZN such that un(· + yn) does not converge weakly to 0 in D2,2(RN). Since un(· + yn) is bounded, there is u0 6= 0 such that, up to a subsequence,

un(· + yn) ⇀ u0

in D2,2(RN),

as n → ∞. We ﬁnd y ∈ RN such that u0χB(y,r) 6= 0 in L2(B(y,r)). Observe that, passing to a subse- quence, we may assume that un(· + yn) → u0 in L2(B(y,r)). Then, in view of (4.1)

|un(· + yn)|2 dx =

|un|2 dx → 0

## ZB(y,r)

## ZB(yn+y,r)

as n → ∞, which contradicts the fact un(· + yn) → u0 6= 0 in L2(B(y,r)). Therefore un(· + yn) ⇀ 0 in (cid:3) D2,2(RN) for any (yn) ⊂ ZN and by Lemma 4.2 we conclude.

- 5. Proof of Theorem 1.3
In this section we adapt a variational approach from [20, Section 3] for the bi-Laplacian. Let

G−(s) :=

## (R R

## Notice that G+, G− ≥ 0 and G = G+ − G−.

s 0 max{−g(t),0}dt 0 s max{g(t),0}dt

## for s ≥ 0, for s < 0.

First, we sketch our approach with an approximation Jε of J and present some auxiliary lemmas. The

proof of Theorem 1.3 is postponed to the end of the section. Let

g+(s) := G′ s 0 g−(t)dt ≥ 0, for s ∈ R. In view of (g1) and (g3), there is some c > 0 such that for

## s ∈ R.

## and

+(s)

g−(s) := g+(s) − g(s),

Notice that G−(s) = every s ∈ R

## R

|G+(s)| ≤ c|s|2∗∗

(5.1) so G+(u) ∈ L1(RN) whenever u ∈ D2,2(RN) ⊂ L2∗∗ integrable, for u ∈ D2,2(RN), unless G−(u) ≤ c|u|2∗∗

,

(RN). On the other hand, G−(u) may not be for some c > 0. To overcome this problem, for

11

(cid:3)

12

## J. MEDERSKI AND J. SIEMIANOWSKI

ε ∈ (0,1), we deﬁne ϕε : R → [0,1] by

ϕε(s) :=

∗∗−1|s|2∗∗−1 ε2 1 (

1

## for |s| ≤ ε, for |s| ≥ ε.

We introduce a new functional

(5.2)

## where Gε

(5.3)

−(s) :=

## R

1 2

|∆u|2 +

## Gε

Jε(u) :=

−(u)dx −

## RN

## RN

## RN

## Z

## Z

## Z

## s

0 ϕε(t)g−(t)dt, s ∈ R. By (g0), there is c(ε) > 0 such that |ϕε(s)g−(s)| ≤ c(ε)|s|2∗∗−1,

## s ∈ R.

G+(u)dx,

−(s) ≤ c(ε)|s|2∗∗

This implies that Gε for ε ∈ (0,1), Jε is well-deﬁned on D2,2(RN), continuous and J′ v ∈ C∞ v ∈ C∞

for any s ∈ R and some constant c(ε) > 0 depending on ε > 0. Hence, ε(u)(v) exists for any u ∈ D2,2(RN) and ε(u)(v) = 0 for any

0 (RN). Therefore, we say that u is a critical point of Jε provided that J′ 0 (RN). We deﬁne, for ε ∈ (0,1),

## Gε

:= G+ − Gε −,

## Mε

## Pε

## cε

:=

u ∈ D2,2(RN) \ {0} :

:=

## n

u ∈ D2,2(RN) :

## n := inf u∈Mε

## Jε(u).

## Z

## RN

|∆u|2 − 2∗∗

## RN

## Z Gε(u)dx > 0

## RN

Z 6= ∅,

## o

## Gε(u)dx = 0

## o

,

and introduce the map mPε : Pε → Mε given by

mPε(u) = u(rε·),

## where

2∗∗

RN Gε(u)dx RN |∆u|2 R We check that mPε is well-deﬁned. If u ∈ Pε, then R

## rε = rε(u) :=

(cid:18)

(cid:19)

1/4

=

(cid:0)

2∗∗

## R

## RN Gε(u)dx kuk1/2

(cid:1)

1 4

.

## Z

## RN

|∆(mPε(u)(x)|2 dx = r4−N

## ε

=

2∗∗

(cid:18)

=

2∗∗

(cid:18)

## Z

## RN

## Z

## RN

## Z

## RN

|∆u|2 dx

## Gε(u)dx

## Gε(u)dx

(cid:19)

(cid:19)

4−N 4

## kuk

## N−4 2 kuk2

## kuk

## N 2

2∗∗

## RN Gε(u)dx

## N 4

=

2∗∗

(cid:18) = 2∗∗

## Z

## Z

## RN

## Gε(u)dx

(cid:19)

## (cid:0) r−N ε

## RN

## Gε(mPε(u)(x))dx.

## R

(cid:1)

LEMMA 5.1. For every δ > 0 there is cδ > 0 such that

Gε(u + v) − Gε(u) − δ|u|2∗∗

≤ cδ|v|2∗∗

## for all u,v ∈ R.

(cid:3)

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

PROOF. First, we show that for every δ > 0 there is c(δ) > 0 such that

−(u)| ≤ δ|u|2∗∗

+ c(δ)|v|2∗∗

−(u + v) − Gε

## |Gε

(5.4) Fix δ > 0 and u, v ∈ R. By the mean value theorem, there is θ ∈ (0,1) such that

,

## u, v ∈ R.

## |Gε

−(u + v) − Gε

−(u)| ≤ |ϕε(u + θv)g−(u + θv)||v| ≤ c(ε)|u + θv|2∗∗−1|v| ≤ c1(ε)|u|2∗∗−1|v| + c1(ε)|v|2∗∗

,

where we used (5.3). We exploit the Young inequality with δ/c1(ε)

|u|2∗∗−1|v| ≤

## δ c1(ε)

|u|(2∗∗−1)p + c2(δ,ε)|v|q, where p =

2∗∗ 2∗∗ − 1

, q = 2∗∗,

to obtain

## |Gε

−(u + v) − Gε

−(u)| ≤ δ|u|2∗∗

+ c3(δ,ε)|v|2∗∗

,

what proves the assertion.

Now, we show that for every δ > 0 there is c(δ) > 0 such that ≤ c(δ)|v|2∗∗

G+(u + v) − G+(u) − δ|u|2∗∗

,

## u, v ∈ R.

Fix δ > 0 and u, v ∈ R. By (g1) and (g3), there are 0 < η < M such that

G+(s) ≤

2

22∗∗ δ|s|2∗∗

,

if |s| < η or |s| > M. We consider four cases. Case I: |u + v| < η or |u + v| > M. We use the fact that G+ ≥ 0 and obtain

G+(u + v) − G+(u) ≤ G+(u + v) ≤

2

22∗∗ δ|u + v|2∗∗

what proves the assertion. Case II: η ≤ |u + v| ≤ M and |v| > M. There is c > 0 such that G+(s) ≤ c|s|2∗∗

## , for every s ∈ R, so

## ≤ δ

|u|2∗∗ (cid:16)

+ |v|2∗∗

(cid:17)

,

G+(u + v) − G+(u) ≤ G+(u + v) ≤ c|u + v|2∗∗

≤ cM2∗∗

≤ c|v|2∗∗

and we are done. Case III: η ≤ |u + v| ≤ M and η/2 ≤ |v| ≤ M. The set C := C → R, given by h(u,v) := G+(u+v)−G+(u)−δ|u|2 |v|2 max(u,v)∈C h(u,v) ≤ c(δ) and we are done. Case IV: η ≤ |u + v| ≤ M and |v| < η/2. By the continuity of g+ and by (g0), there is c(η) such that |g+(s)| ≤ c(η)|s|2∗∗−1,

(u,v) ∈ R2 | η ≤ |u + v| ≤ M and η/2 ≤ |v| ≤ M

is compact and the function h :

∗∗

, is continuous. Thus, there is c(δ) > 0 such that

(cid:8)

(cid:9)

∗∗

## η 2

|s| ≥

.

By the mean value theorem, there is θ ∈ (0,1) such that

G+(u + v) − G+(u) = g+(u + θv)v.

Notice that |u + θv| ≥ |u + v| − (1 − θ)|v| > η − η/2 = η/2, so combining the above we obtain

G+(u + v) − G+(u) ≤ c(η)|u + θv|2∗∗−1|v|.

We then proceed as in the ﬁrst part of the proof.

13

14

## J. MEDERSKI AND J. SIEMIANOWSKI

Finally, we use the above results to deduce

Gε(u + v) − Gε(u) = G+(u + v) − G+(u) −

≤ δ|u|2∗∗

+ c(δ)|v|2∗∗

Gε −(u + v) − Gε

−(u + v) − Gε

−(u) −(u)|

+ |Gε (cid:0)

(cid:1)

≤ 2

δ|u|2∗∗

+ c(δ)|v|2∗∗

.

(cid:16)

(cid:17)

LEMMA 5.2. Suppose that (un) ⊂ Mε, Jε(un) → cε and

## un ⇀

u 6= 0 in D2,2(RN), un(x) →

## u(x)

## for a.e. x ∈ RN

## for some

u ∈ D2,2(RN). Then un →

u,

u is a critical point of Jε and Jε(

## u) = cε.

## e

## e

PROOF. It follows, by Lemma 5.1, that for every δ > 0 theres is c(δ) > 0 such that

## e

e e |Gε(u + v) − Gε(u)| ≤ δ|u|2∗∗ 0 (RN) and t ∈ R we observe that (Gε(un + tv) − Gε(un)) is uniformly integrable

## e u, v ∈ R.

+ c(δ)|v|2∗∗

,

Thus taking any v ∈ C∞ and tight. In view of Vitali’s convergence theorem we have

## lim n→∞

RN Since each un ∈ Mε, we get 1 2

## Z

## cε ← Jε(un) =

## so

## Gε(un + tv) − Gε(un)dx =

## Z

## RN

## Gε(

## u + tv) − Gε(

## Z

## RN

|∆un|2 dx −

## Z

## RN

## Gε(un)dx =

## e

(cid:18)

2∗∗ 2

− 1

(cid:19)Z

## u)dx.

## e

## RN

Gε(un)dx,

(5.5)

A := lim n→∞

Combining the above we have

## Z

## RN

## Gε(un)dx =

1 2∗∗

(cid:18)

1 2

−

1 2∗∗

(cid:19)

−1

cε > 0.

(5.6)

## lim n→∞

## Z

## RN

Gε(un + tv)dx = lim n→∞

## Z

## RN

## Gε(un)dx +

## Z

## RN

## Gε(

## u + tv)dx −

## Z

## RN

## Gε(

## u)dx

= A +

## Z

## RN

## Gε(

## u + tv)dx −

## Z

## RN

## Gε( e

## u)dx.

## e

By (5.5) and Lemma 5.1, un + tv ∈ Pε for sufﬁciently large n and sufﬁciently small |t|. Thus and by (5.6), e for sufﬁciently small |t|, we have

## e

## lim n→∞

1 t (cid:18)Z

## RN

## Gε(un + tv)dx

(cid:19)

## N−4 N

−

(cid:18)Z

## RN

## Gε(un)dx

(cid:19)

## N−4 N

!

1 t (cid:18)

=

A +

## Gε(

## u + tv)dx −

## Gε(

## RN

## RN

## Z

Z and, consequently, by the Lebesgue dominated convergence theorem (5.7)

## e

## u)dx

## e

(cid:19)

## N−4 N

## − A

## N−4 N

!

.

## 1 t (cid:18) where gε := G′

## lim t→0

A +

## Gε(

## Gε(

## u + tv)dx −

## RN

## RN

## Z

## Z

## ε = g+ − ϕεg−.

e If un + tv ∈ Pε, then Jε(mPε(un + tv)) ≥ cε, so

## u)dx

## e

(cid:19)

## N−4 N

## − A

## N−4 N

!

=

## N − 4 N

## A

−4 N

## Z

## RN

## gε(

u)v dx,

## e

## rε(un + tv)4−N

(cid:18)

1 2

−

1 2∗∗

(cid:19)Z

## RN

|∆(un + tv)|2 dx ≥ cε.

(cid:3)

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

15

Raising both sides to the 4/N-power yields

## 4 N

1 2

1 2∗∗

4 |∆(un + tv)|2 dx ≥ c N ε

(5.8)

−

## RN

## (cid:19) Assumptions un ∈ Mε and Jε(un) → cε imply that

## Z

(cid:18)

(cid:18)

2∗∗

## Z

## RN

## Gε(un + tv)dx

(cid:19)

## N−4 N

.

(5.9)

For all n and t, we have

## Z

## RN

## |∆un|2 dx → cε

(cid:18)

1 2

−

1 2∗∗

(cid:19)

−1

.

## t 2

|∆v|2 dx =

## ∆un∆v dx +

## RN

## RN

## Z

## Z

Hence, by (5.8) and since un ∈ Mε, for t > 0,

1 2t

(cid:18)Z

## RN

|∆(un + tv)|2 dx −

## Z

## RN

## |∆un|2 dx

(cid:19)

.

## t 2

|∆v|2 dx ≥

## ∆un∆v dx +

## RN

## RN

## Z −4 N

Z 1 2t Letting n → ∞, by (5.6), (5.5) and (5.9), we deduce that, for sufﬁciently small t > 0,

## N−4 N

1 2∗∗

1 2

## 4 N c ε

2∗∗

2∗∗

−

## Gε(un + tv)dx

−

## Gε(un)dx

## RN

## RN

(cid:18)

(cid:18)

(cid:18)

(cid:19)

(cid:19)

## Z

## Z

(cid:19)

## N−4 N

(cid:18)Z

## RN

## |∆un|2 dx

(cid:19)

## 4 N

## t 2

|∆v|2 dx

∆

## u∆v dx +

## RN

## RN

## Z

## Z

−4 N

## N−4 N

1 2

1 e ≥ 2t

1 2∗∗

## 4 N c ε

## N−4 N

2∗∗

− (2∗∗A)

## Gε(

## u)dx

## Gε(

A +

## u + tv)dx −

−

## RN

(cid:18)

## RN

(cid:19)

(cid:18)

(cid:19)(cid:19)

## Z

(cid:18)

## Z N−4 N

2∗∗ 2

## e N−4 N

## e Gε(

1 t (cid:18)

## 4 N

## A

## Gε(

A +

=

## u + tv)dx −

## − A

.

## u)dx

## RN

## RN

!

Z We pass to the limit as t → 0+ and use (5.7) to get N − 4 N 0 (RN) was arbitrary we infer that e

## Z

(cid:19)

## e

## e

2∗∗ 2

## u)v dx =

## u)v dx.

∆

## gε(

## gε(

## u∆v dx ≥

## RN

## RN

## RN

## Z

## Z

## Z

Since v ∈ C∞ Theorem 1.2 to the equation ∆2u = gε(u) with Gε ∈ L1(RN), to deduce that

u is a critical point of Jε. We use the Pohožaev identity e u ∈ Mε, what leads to

## e

!

## cε ≤ Jε(

u) =

(cid:18)

1 2

−

1 2∗∗

(cid:19)Z

## RN

|∆

## e

u|2 dx ≤ liminf n→∞

where the weak l.s.c of the norm was used. Thus, Jε(

## e

## e

1 2

1 2∗∗

|∆un|2 dx = lim n→∞

−

## e

## RN

## (cid:18) (cid:19)Z u) = cε and kunk → k

## uk, so un →

Jε(un) = cε,

u in D2,2(RN). (cid:3)

e PROOF OF THEOREM 1.3. Take a minimizing sequence (un) in Mε of Jε, i.e., Jε(un) → cε. Since

## e

## e

un ∈ Mε, n ≥ 1, we have

1 2

1 2∗∗

−

## Jε(un) =

RN (cid:19)Z and so (un) is bounded in D2,2(RN). Moreover, we have

(cid:18)

|∆un|2 dx → cε,

1 2∗∗

1 2

2∗∗

|∆un|2 dx →

−

## G+(un)dx ≥

## cε.

## RN

## RN

(cid:19)

## Z

(cid:18)

## Z

By the assumption G+ satisﬁes (4.2), so (4.1) is not satisﬁed. Passing to a subsequence, we may choose (yn) in RN and 0 6= uε ∈ D2,2(RN) such that un(· + yn) ⇀ uε

for a.e. x ∈ RN,

in D2,2(RN),

## un(x + yn) → uε(x)

!

.

16

## J. MEDERSKI AND J. SIEMIANOWSKI

as n → ∞. In view of Lemma 5.2, uε ∈ Mε is a critical point of Jε at the level cε.

Choose εn → 0+. Fix an arbitrary u ∈ M. Since Gε(s) ≥ G(s), for all s ∈ R and ε ∈ (0,1), we

## deduce that

## Gεn(u)dx ≥

RN Z so mPεn(u) ∈ Mεn is well-deﬁned. We have

## RN

## Z

## G(u)dx =

1 2∗∗

## Z

## RN

|∆u|2 dx > 0,

## Jεn(uεn) ≤ Jεn(mPεn(u)) =

(cid:18)

1 2

−

1 2∗∗

(cid:19)(cid:18)

2∗∗

## RN Gεn(u)dx RN |∆u|2 dx R R

## rεn(u)4−N

(cid:19)

4−N 4

## Z

## RN

|∆u|2 dx

=

≤

(cid:18)

(cid:18)

1 2

1 2

−

−

1 2∗∗

1 2∗∗

(cid:19)(cid:18)Z

(cid:19)(cid:18)Z

## RN

## RN

|∆u|2 dx

|∆u|2 dx

(cid:19)

(cid:19)

N | 4

## N 4

(cid:18)

(cid:18)

2∗∗

## {z Gεn(u)dx

− N−4 } 4

2∗∗

## Z

## RN

## G(u)dx

(cid:19) − N−4 4

## Z

## RN

=(RRN |∆u|2 dx)

(cid:19) − N−4 4

=

(cid:18)

1 2

## Thus Jεn(uεn) ≤ infM J and

−

1 2∗∗

(cid:19)Z

## RN

|

|∆u|2 dx = J(u).

## {z

}

1 2

1 2∗∗

## |∆uεn|2 dx ≤

(5.10)

−

inf M We have Gε(s) ≤ G1/2(s), for all s ∈ R and ε ∈ (0,1/2), so

## RN

## Z

(cid:18)

(cid:19)

−1

J,

## for every n.

G1/2(uε)dx ≥

## RN

Z and some calculations yield

## Z

## RN

## Gε(uε)dx =

1 2∗∗

## Z

## RN

|∆uε|2 dx > 0 =⇒ uε ∈ P1/2,

Jε(uε) ≥ J1/2(mP1/2(uε)) ≥ J1/2(u1/2).

Therefore, we get

−1

−1

1 2∗∗

1 2

1 2

1 2∗∗

## |∆uεn|2 dx =

2∗∗

−

−

## G+(uεn)dx ≥

J1/2(u1/2) > 0.

## Jεn(uεn) ≥

## RN

## RN

(cid:19)

## Z

(cid:18)

(cid:19)

## Z

(cid:18) By (5.10), (uεn) is bounded in D2,2(RN) and RN G+(uεn)dx > c > 0, for some constant c. In view of Lemma 4.1, (4.1) is not satisﬁed. Passing to a subsequence, there is (yn) in RN such that uεn(· + yn) ⇀ u0 6= 0 and uεn(x+yn) → u0(x) a.e. in RN. We write un := uεn(·+yn) for short. Since g− is continuous and g−(0) = 0, one may check that, for every v ∈ C∞ un|2∗∗−1χ{| |

## R

0 (RN), e χ{|

1 ε2∗∗−1 n

## a.e. in RN

## un)v

≤

## un|≤εn}g−( e

## un|≤εn}g−( e

## un)v

→ 0

(cid:12) (cid:12) (cid:12) (cid:12)

(cid:12) (cid:12) (cid:12) (cid:12) un)v − g−(u0)v un|2∗∗−1 e

(cid:12) (cid:12)

(cid:12) (cid:12) a.e. in RN.

## and

## e

## e

## e

un|>εn}g−( e Due to the estimate |g−( 1 + | tight because of the compact support). In view of Vitali’s convergence theorem

## χ{| un)v| ≤ c

## → 0 |v|, the family {g−(

un)v} is uniformly integrable (and

(cid:12) (cid:12)

(cid:12) (cid:12)

## Z

## RN

≤

## |ϕεn(

## un)g−(

## Z

1 e ε2∗∗−1 RN (cid:12) n (cid:12) (cid:12) (cid:12)

(cid:0)

## e

## un)v − g−(u0)v| dx

## e

un|2∗∗−1χ{| e |

## un|≤εn}g−( e

e

## un)v

e

(cid:1)

(cid:12) (cid:12) (cid:12) (cid:12)

## dx +

## Z

## RN

(cid:12) (cid:12)

χ{|

## e

## un|>εn}g−( e

## un)v − g−(u0)v

e

(cid:12) (cid:12)

dx → 0,

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

as n → ∞. Similarly, we obtain

Z Gathering the above we deduce that

## RN

g+(

## un)v dx →

## e

## Z

## RN

## g+(u0)v dx.

## J′ εn(

un)(v) =

## Z

## RN

∆

## un∆v dx −

## RN

## Z

g+(

## un)v dx +

## Z

## RN

## ϕεn(

## un)g−(

## un)v dx

## e

→

## Z

## RN

## ∆u0∆v dx −

## e

## Z

## RN

## g+(u0)v dx +

## e

## Z

## RN

## g−(u0)v dx. e e

## Each

un is a critical point of Jεn, since so is uεn (translation invariance), hence

g(u0)v dx,

## ∆u0∆v dx =

## e

## RN

## RN

## Z

## Z

i.e., u0 is a weak solution to (1.1). By Lebesgue’s dominated convergence theorem one may show that

## Gεn − (

un) → G−(u0)

a.e. in RN,

as n → ∞, and, on the other hand,

2∗∗

## Z

## RN

## Gεn − (

un)dx = 2∗∗

## Z

## RN

## e G+(

## un)dx −

## Z

## RN

|∆

## un|2 dx ≤ c

(cid:18)

## sup n≥1

## unkD2,2(RN) k

(cid:19)

< ∞,

where we used the fact that

## e

un ∈ Mεn, (5.1) and (5.10). By Fatou’s lemma and by the above e

## e

## e

## e Z

## RN

G−(u0)dx ≤ liminf n→∞

## Z

## RN

## Gεn − (

un)dx < ∞,

namely, we have shown that G−(u0) ∈ L1(RN). By the Pohožaev identity, we infer that u0 ∈ M. Lastly, we show that J(u0) = infM J. We use the weak l.s.c. of the norm and (5.10) to ﬁnd that

## e

1 2

J(u0) =

−

(cid:18) = liminf n→∞

1 2∗∗ (cid:19)Z 1 − 2

(cid:18)

RN 1 2∗∗

|∆u0|2 dx ≤ liminf n→∞

(cid:18)

1 2

(cid:19)Z

## RN

## |∆uεn|2 dx ≤ inf M

−

J.

1 2∗∗

(cid:19)Z

## RN

|∆

## un|2 dx

## e

- 6. Biharmonic logarithmic inequality
## LEMMA 6.1. If u ∈ D2,2(RN) and

RN |u|2 dx = 1, then

R |∇u|2 dx <

|∆u|2 dx

1/2

.

## Z

## RN

(cid:18)Z

## RN

(cid:19)

PROOF. We rely on ideas from [4]. Let us deﬁne the Fourier transform

## u of u (whenever possible) as

u(ξ) =

1 (2π)N/2

## Z

## RN

e−ix·ξu(x)dx,

## ξ ∈ RN. b

## If u ∈ D2,2(RN) and

RN |u|2 dx = 1, then u ∈ H2(RN) and by the Plancharel theorem

## b

## R

kukL2(RN) = k

ukL2(RN),

k∇ukL2(RN) = k

k∆ukL2(RN) = k

∇ukL2(RN) = kξ b ∆ukL2(RN) = k|ξ|2 c b

ukL2(RN),

## ukL2(RN).

c

b

17

(cid:3)

18

## J. MEDERSKI AND J. SIEMIANOWSKI

By the Cauchy–Schwartz inequality we get

1/2

1/4

1/4

## |ξ

u(ξ)|2 dξ

≤

||ξ|2

u(ξ)|2 dξ

u(ξ)|2 dξ |

.

(cid:18)Z

## RN

(cid:19)

(cid:18)Z

## RN

(cid:19)

(cid:18)Z

## RN

(cid:19)

and the assertion follows with the non-strict inequality. Recall that the equality in the Cauchy–Schwartz b b inequality holds if and only if |ξ|2 u = 0. Hence the inequality in (cid:3) the statement is in fact strict.

## b

## u(ξ) for some λ, what implies

u(ξ) = λ

## b

## b

Proof of Theorem 1.4. Observe that the following inequality holds

## b

(6.1)

## where

(cid:16)Z

## RN

|∆u|2 dx

(cid:17)

## N

## N−4 ≥ CN,log

CN,log = 2∗∗

## Z

## RN

1 2

−

|u|2 log|u|dx,

1 2∗∗

− 4

## N−4(inf M

for any u ∈ D2,2(RN),

J)

4 N−4.

(cid:17) Indeed, it is enough to consider u ∈ D2,2(RN) such that M, where

(cid:16)

RN |u|2 log|u|dx > 0. We then obtain u(r·) ∈

## R

1/4

2∗∗

## RN |u|2 log |u|dx

r :=

.

RN |∆u|2

## R

(cid:18)

(cid:19)

Hence J(u(r·)) ≥ infM J and we get (6.1). Now note that (6.1) is equivalent to

## R

## N

e−α2∗∗

## N−4 ≥ CN,log max α∈R

## for u ∈ D2,2(RN).

|∆u|2 dx

## |eαu|2 log |eαu|dx

,

(6.2)

## RN

## RN

## Z

(cid:16)Z

## n

## o

(cid:17)

RN |u|2 dx = 1, the maximum of the right hand side of (6.2) is attained at α = N−4

Assuming that RN |u|2 log |u|dx. Hence we get R N N − 4

N − 4 8

## R

≥ log(CN,log) − α2∗∗ + 2α + log

|∆u|2 dx

## log

## RN

(cid:16)Z

(cid:16)

(cid:17)

(cid:17)

that is

8 −

## and

## N N − 4

## log

(cid:16)Z

## RN

|∆u|2 dx

(cid:17)

## ≥ log

(cid:16)

## CN,log

N − 4 8

e−1

(cid:17)

+

8 N − 4

## Z

## RN

## |u|2 log|u|dx

## N 8

## log

thus (1.7) holds.

(cid:16)Z

## RN

|∆u|2 dx

(cid:17)

≥

N − 4 8

## log

(cid:16)

## CN,log

N − 4 8

e−1

(cid:17)

+

## Z

## RN

## |u|2 log |u|dx

We show that the constant in (1.7) is optimal, i.e., there is u ∈ D2,2(RN) such that the equality holds. First of all, notice that if u0 is a minimizer given by Theorem 1.3, then for u0 we have the equality in (6.1):

(6.3)

|∆u0|2 dx

## N N−4

## = CN,log

|u0|2 log |u0|dx.

(cid:18)Z

## RN

We use (6.1) for the family of functions

## (cid:19) eα ku0kL2

RN u0 ∈ D2,2(RN), α ∈ R, to get

## Z

## N N−4

## ≥ CN,logku0k2∗∗−2

|∆u0|2 dx

(6.4)

## L2

## RN

(cid:18)Z

(cid:19) Now let us consider the function f : R → R given by

e(2−2∗∗)α

## Z

f(α) := CN,logku0k2∗∗−2

## L2

e(2−2∗∗)α

## Z

## RN

## |u0|2 log

(cid:12) (cid:12) (cid:12) (cid:12)

## eα ku0kL2

## RN

## u0

## |u0|2 log

## dx −

(cid:12) (cid:12) (cid:12) (cid:12)

(cid:12) (cid:12) (cid:12) (cid:12)

## eα ku0kL2

## dx, α ∈ R.

## u0

(cid:12) (cid:12) (cid:12) (cid:12) |∆u0|2 dx

## N N−4

(cid:18)Z

## RN

(cid:19)

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

## Note that

2

N − 4 8 On the other hand, f attains maximum at α = log(ku0kL2) in view of (6.4) and (6.3), thus

u0 ku0kL2 (cid:12) (cid:12) (cid:12) (cid:12) N − 4 8

u0 ku0kL2 (cid:12) (cid:12) (cid:12) (cid:12)

f′(α) = 0 ⇐⇒ α =

## log

−

## dx.

RN (cid:12) (cid:12) (cid:12) (cid:12)

(cid:12) (cid:12) (cid:12) (cid:12)

## Z

2

u0 ku0kL2 (cid:12) (cid:12) (cid:12) (cid:12) |∆u0|2 dx =

u0 ku0kL2 (cid:12) (cid:12) (cid:12) (cid:12)

## log

## dx =

## − log(ku0kL2)

RN (cid:12) Z (cid:12) (cid:12) (cid:12)

(cid:12) (cid:12) (cid:12) (cid:12)

or, equivalently,

## 1 ku0k2

## N 4

,

## RN

L2 Z where we used the fact that u0 ∈ M. Therefore we obtain the equality in (1.7) for the function

## u0 ku0kL2

Let us now suppose that

(N−4)/N

## N 8

## 8e CN,log(N − 4)

## log

(cid:18)

(cid:19)

Z for some u ∈ D2,2(RN) such that kukL2(RN) = 1. Then

## RN

|∆u|2 dx

!

=

## Z

## RN

## |u|2 log |u|dx

## N

## N−4 = CN,loge−α2∗∗

|∆u|2 dx

## |eαu|2 log |eαu|dx

## RN

## RN

(cid:16)Z

Z RN |u|2 log |u|dx and the equality in (6.1) holds for u1 := eαu. Hence J(u0) = infM J

(cid:17)

## for α = N−4 for

8 −

## R

1/4

## RN |u1|2 log |u1|dx RN |∆u1|2 dx

2∗∗

## u0 := u1(r·) ∈ M, where r =

.

## R R

(cid:18)

(cid:19)

0 (RN), G(u0+v) ∈ 0 (RN). We use the fact that G is C1-smooth and

Let us sketch the proof that u0 is a critical point of J. Firstly, note that, for every v ∈ C∞ L1(RN), for G(s) := s2 log |s|. Fix an arbitrary v ∈ C∞ the Lebesgue dominated convergence theorem to get

## lim t→0

## 1 t

(cid:18)Z

## RN

## G(u0 + tv)dx −

## Z

## RN

## G(u0)dx

(cid:19)

=

## Z

## RN

## g(u0)v dx.

By the continuity,

RN G(u0 + tv)dx > 0, for sufﬁciently small |t| > 0, so (u0 + tv)(r·) ∈ M, where

## R

## r =

(cid:18)

2∗∗

RN G(u0 + tv)dx RN |∆(u0 + tv)|2 dx

## R

(cid:19)

1/4

.

## Hence

## R

J((u0 + tv)(r·)) ≥ inf M

J = J(u0)

or, equivalently,

4/N

1 2

1 2∗∗

|∆(u0 + tv)|2 dx ≥ J(u0)4/N

2∗∗

## G(u0 + tv)dx

−

## RN

## RN

(cid:19)

(cid:18)

(cid:19) We then proceed similarly as in the last part of the proof of Lemma 5.2 to conclude that

(cid:18)

## Z

## Z

(N−4)/N

.

## Z

## RN

## ∆u0∆v dx ≥

## Z

## RN

g(u0)v dx,

which yields that u0 is a critical point of J.

.

19

20

## J. MEDERSKI AND J. SIEMIANOWSKI

Finally, we show the estimate of the constant CN,log from Theorem 1.7. Observe that if u ∈ D2,2(RN) RN |u|2 dx = 1, then u ∈ H2(RN). In view of Lemma 6.1 and the logarithmic Sobolev inequality

and (1.8) we obtain

## R

## RN

## Z and so

|u|2 log(|u|)dx <

## N 4

## log

## 2 πeN

(cid:18)Z

## RN

|∆u|2 dx

(cid:19)

1/2

!

=

## N 8

## log

(cid:18)(cid:16)

## 2 πeN

(cid:17)

2

## Z

## RN

|∆u|2 dx

(cid:18)

## 8e CN,log(N − 4)

(cid:19)

(N−4)/N

<

(cid:16)

## 2 πeN

(cid:17)

2

.

## Acknowledgements

The authors were supported by the National Science Centre, Poland (Grant No. 2017/26/E/ST1/00817). J. Mederski was also partially supported by the Deutsche Forschungsgemeinschaft (DFG, German Research Foundation) – Project-ID 258734477 – SFB 1173 during the stay at Karlsruhe Institute of Technology.

## References

[1] R. A. Adams, Sobolev spaces, Academic Press [A subsidiary of Harcourt Brace Jovanovich, Publishers], New York-London,

- 1975. Pure and Applied Mathematics, Vol. 65.
[2] S. Agmon, A. Douglis, and L. Nirenberg, Estimates near the boundary for solutions of elliptic partial differential equations

satisfying general boundary conditions. I, Comm. Pure Appl. Math. 12 (1959), 623–727.

[3] S. S. Antman, Nonlinear problems of elasticity, 2nd ed., Applied Mathematical Sciences, vol. 107, Springer, New York, 2005. [4] J. Bellazzini, R. L. Frank, and N. Visciglia, Maximizers for Gagliardo-Nirenberg inequalities and related non-local problems,

Math. Ann. 360 (2014), no. 3-4, 653–673.

[5] H. Berestycki and P.-L. Lions, Nonlinear scalar ﬁeld equations. I. Existence of a ground state, Arch. Rational Mech. Anal. 82

(1983), no. 4, 313–345.

[6] H. Brézis and T. Kato, Remarks on the Schrödinger operator with singular complex potentials, J. Math. Pures Appl. (9) 58

(1979), no. 2, 137–151.

[7] H. Brezis and E. H. Lieb, Minimum action solutions of some vector ﬁeld equations, Comm. Math. Phys. 96 (1984), no. 1,

97–113.

[8] E. A. Carlen, Superadditivity of Fisher’s information and logarithmic Sobolev inequalities, J. Funct. Anal. 101 (1991), no. 1,

194–211. MR1132315

[9] M. del Pino and J. Dolbeault, Best constants for Gagliardo-Nirenberg inequalities and applications to nonlinear diffusions, J.

Math. Pures Appl. (9) 81 (2002), no. 9, 847–875.

[10] M. del Pino and J. Dolbeault, The optimal Euclidean Lp-Sobolev logarithmic inequality, J. Funct. Anal. 197 (2003), no. 1,

151–161.

[11] G. Fibich, B. Ilan, and G. Papanicolaou, Self-focusing with fourth-order dispersion, SIAM J. Appl. Math. 62 (2002), no. 4,

1437–1462.

[12] F. Gazzola, H.-C. Grunau, and G. Sweers, Polyharmonic boundary value problems, Lecture Notes in Mathematics, vol. 1991, Springer-Verlag, Berlin, 2010. Positivity preserving and nonlinear higher order elliptic equations in bounded domains.

[13] L. Gross, Logarithmic Sobolev inequalities, Amer. J. Math. 97 (1975), no. 4, 1061–1083. [14] E. H. Lieb and M. Loss, Analysis, 2nd ed., Graduate Studies in Mathematics, vol. 14, American Mathematical Society, Provi-

## dence, RI, 2001.

[15] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. II, Ann. Inst.

H. Poincaré Anal. Non Linéaire 1 (1984), no. 4, 223–283.

[16] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. I, Ann. Inst. H.

## Poincaré Anal. Non Linéaire 1 (1984), no. 2, 109–145.

[17] S. Mayboroda and V. Maz’ya, Regularity of solutions to the polyharmonic equation in general domains, Invent. Math. 196

(2014), no. 1, 1–68.

[18] V. G. Maz’ja, Sobolev spaces, Springer Series in Soviet Mathematics, Springer-Verlag, Berlin, 1985. Translated from the

## Russian by T. O. Shaposhnikova.

[19] J. Mederski, Nonradial solutions of nonlinear scalar ﬁeld equations, Nonlinearity 33 (2020), no. 12, 6349–6380. [20] J. Mederski, General class of optimal Sobolev inequalities and nonlinear scalar ﬁeld equations, J. Differential Equations 281

(2021), 411–441.

(cid:19)

,

(cid:3)

## BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS

[21] V. V. Meleshko, Selected topics in the history of the two-dimensional biharmonic problem, Appl. Mech. Rev. 56 (2003), 33-85. [22] L. Nirenberg, Estimates and existence of solutions of elliptic equations, Comm. Pure Appl. Math. 9 (1956), 509–529. [23] P. Pucci and J. Serrin, A general variational identity, Indiana Univ. Math. J. 35 (1986), no. 3, 681–703. [24] A. P. S. Selvadurai, Partial differential equations in mechanics. 2, Springer-Verlag, Berlin, 2000. The biharmonic equation,

## Poisson’s equation.

[25] R. C. A. M. Van der Vorst, Best constant for the embedding of the space H2 ∩ H1

## 0(Ω) into L2N/(N−4)(Ω), Differential

## Integral Equations 6 (1993), no. 2, 259–276.

[26] F. B. Weissler, Logarithmic Sobolev inequalities for the heat-diffusion semigroup, Trans. Am. Math. Soc. 237 (1978), 255–

269.

(J. Mederski) INSTITUTE OF MATHEMATICS, POLISH ACADEMY OF SCIENCES, UL. ´SNIADECKICH 8, 00-656 WARSAW, POLAND AND DEPARTMENT OF MATHEMATICS, KARLSRUHE INSTITUTE OF TECHNOLOGY (KIT), D-76128 KARLSRUHE, GERMANY Email address: jmederski@impan.pl

(J. Siemianowski) FACULTY OF MATHEMATICS AND COMPUTER SCIENCES, NICOLAUS COPERNICUS UNIVERSITY IN TORU ´N UL. GAGARINA 11, 87-100 TORU ´N, POLAND AND INSTITUTE OF MATHEMATICS, POLISH ACADEMY OF SCIENCES, UL. ´SNIADECKICH 8, 00-656 WARSAW, POLAND

## Email address: jsiem@mat.umk.pl

21

