## Biharmonic nonlinear scalar field equations

Jarosław Mederski and Jakub Siemianowski

ABSTRACT. We prove a Brezis-Kato-type regularity result for weak solutions to the biharmonic nonlinear equation

<!-- formula-not-decoded -->

with a Carathéodory function g : R N × R → R , N ≥ 5 . The regularity results give rise to the existence of ground state solutions provided that g has a general subcritical growth at infinity. We also conceive a new biharmonic logarithmic Sobolev inequality

<!-- formula-not-decoded -->

for a constant 0 &lt; C &lt; ( 2 πeN ) 2 and we characterize its minimizers.

## 1. Introduction

The study of higher-order differential elliptic operators is important, e.g. in nonlinear elasticity [ 3 ], low Reynolds number hydrodynamics, in structural engineering [ 21 , 24 ] as well as in nonlinear optics [ 11 ], and has attracted attention from the mathematical point of view [ 12 ]. The methods developed for the second order problem, e.g. involving the Laplacian -∆ , may no longer be available. For instance, it is the wellknown that the bi-Laplacian ( -∆) 2 = ∆ 2 cannot be studied by means of some classical methods such as maximum principles, Polya-Szeg˝ o inequalities, or even if (∆ u ) 2 ∈ L 1 ( R N ) , then it is possible that ∆ | u | / ∈ L 1 loc ( R N ) .

The first aim is of this work is to establish a regularity result in the spirit of Brezis-Kato [ 6 ] of weak solutions to

<!-- formula-not-decoded -->

where Ω ⊂ R N is a domain, N ≥ 2 and g : Ω × R → R is a Carathéodory function. If we suppose that Ω is bounded, then there is an extensive literature devoted to this problem. Namely, recall that if g ( x, u ) = f ( x ) , then Agmon, Douglis, Nirenberg [ 2 ] showed that for 1 &lt; q &lt; ∞ , f ∈ L q (Ω) , there exists a unique strong solution u ∈ W 2 , 2 0 (Ω) ∩ W 4 ,q (Ω) to (1.1) provided that ∂ Ω ∈ C 4 see also [ 12 , Corollary 2.21] and references therein. Recently Mayboroda and Maz'ya [ 17 ] showed L ∞ -estimates of u (resp. ∇ u ), where f ∈ C ∞ 0 (Ω) , Ω is an arbitrary bounded domain and N = 4 , 5 (resp. N = 2 , 3 ). To the best of our knowledge, a variant of Brezis-Kato result [ 6 ] for (1.1) is known only on a bounded domain in a particular case. Namely, Van der Vorst [ 25 ] showed that, if N ≥ 5 , g ( x, u ) = a ( x ) u and a ( x ) ∈ L N/ 4 (Ω) , then any weak solution u ∈ W 1 , 2 0 (Ω) ∩ W 2 , 2 (Ω) to (1.1) satisfies u ∈ L q (Ω) for all 1 ≤ q &lt; ∞ . This result is suitable to show the regularity for the biharmonic equation with the nonlinearities of the special form g ( x, u ) = f ( u ) u cf. [ 25 , Lemma B3]. In this paper we give a full answer to the problem on an arbitrary domain and for general g with the adequate Brezis-Kato growth as we shall see below.

2000 Mathematics Subject Classification. 35J91,35J20.

Key words and phrases. Nonlinear scalar field equation, Brezis-Kato reqularity, biharmonic logarithmic Sobolev inequality, critical point theory, Pohozaev manifold.

From now on we assume that Ω ⊂ R N possibly unbounded domain and N ≥ 5 . Inspired by [ 6 ], we impose on g the following growth assumption:

(1.2) | g ( x, s ) | ≤ a ( x ) ( 1 + | s | ) , for s ∈ R and a.e. x ∈ Ω , where 0 ≤ a ∈ L N/ 4 loc (Ω) . The first main result reads as follows.

THEOREM 1.1. Let u ∈ W 2 , 2 loc (Ω) be a weak solution to (1.1) , where g satisfies (1.2) . Then u ∈ C 3 ,α loc (Ω) ∩ W 4 ,q loc (Ω) , for any 0 &lt; α &lt; 1 and 1 ≤ q &lt; ∞ .

It is worth mentioning that in proof of Theorem 1.1 we can no longer apply classical techniques for Laplacian, e.g. due to Brezis and Kato [ 6 ], or Brezis and Lieb [ 7 , Theorem 2.3], since ∆ | u | may not be well-defined for u ∈ W 2 , 2 loc (Ω) . Moreover, the Moser iteration technique does not seem to be applicable straightforwardly for g .

We shall present some consequences of Theorem 1.1 in Ω = R N . Let us define D 2 , 2 ( R N ) as a completion of the space C ∞ 0 ( R N ) with respect to the norm ‖ u ‖ D 2 , 2 := ( ∑ | α | =2 ‖ ∂ α u ‖ 2 L 2 ( R N ) ) 1 2 . By the use of the Fourier transform and the Plancharel theorem we find a constant c &gt; 0 such that, for u ∈ C ∞ 0 ( R N ) ,

<!-- formula-not-decoded -->

Therefore, the norms ‖ u ‖ := ‖ ∆ u ‖ L 2 ( R N ) and ‖ u ‖ D 2 , 2 ( R N ) are equivalent on D 2 , 2 ( R N ) . Moreover, D 2 , 2 ( R N ) is a Hilbert space with the inner product

and u ∈ D 2 , 2 ( R N ) is a weak solution to (1.1) provided that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

As usually expected, the following general Pohožaev-type result holds, cf. [ 23 ].

THEOREM 1.2. Let u ∈ D 2 , 2 ( R N ) be a weak solution to (1.1) , where g satisfies (1.2) . Then

<!-- formula-not-decoded -->

,

provided that ∫ We demonstrate that the Brezis-Kato result for biharmonic Laplacean as well as Theorem 1.2 open the way to study the existence of solutions and their regularity for (1.1). Indeed, let us assume that g is independent of x and the following condition holds:

(

g

0)

G

(

x, u

)

x

·

∂

there is a constant

x

G

(

x, u

c &gt;

0

)

∈

L

1

(

such that

R

|

N

g

(

)

s

, where

)

| ≤

c

G

(

x, s

1 +

|

s

|

) :=

∗∗

2

-

1

s

0

g

(

for x, t

s

∈

<!-- formula-not-decoded -->

)

dt

R

,

x

∈

R

N

,

t

∈

R

.

( ) where 2 ∗∗ := 2 N N -4 . Then a ( x ) := g ( u ( x )) / (1 + | u ( x ) | ) ∈ L N/ 4 loc ( R N ) for u ∈ L 2 ∗∗ ( R N ) and in view of Theorem 1.1, weak solutions to the semilinear problem (1.1) belong to C 3 ,α loc ( R N ) ∩ W 4 ,q loc ( R N ) . We introduce the energy functional

,

where G ( s ) = ∫ s 0 g ( t ) dt . Next, we show the existence of weak solutions to (1.1) under growth assumption at 0 and at infinity inspired by a seminal paper due to Berestycki and Lions [ 5 ] (cf. [ 19 , 20 ]). We assume that g is continuous, g (0) = 0 and ( g 0) holds. Let

<!-- formula-not-decoded -->

and g + ( s ) = G ′ + ( s ) . Suppose in addition, that and the following conditions are satisfied:

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

We introduce the Pohožaev manifold

and in view of Theorem 1.2, M contains all nontrivial solutions. The existence result reads as follows.

<!-- formula-not-decoded -->

THEOREM 1.3. Let ( g 0) -( g 3) be satisfied. Then inf M J &gt; 0 and there is a ground state solution u 0 ∈ D 2 , 2 ( R N ) to (1.1) , i.e. u 0 ∈ M solves (1.1) and J ( u 0 ) = inf M J . Moreover u 0 ∈ C 3 ,α loc ( R N ) ∩ W 4 ,q loc ( R N ) , for any 0 &lt; α &lt; 1 and 1 ≤ q &lt; ∞ .

Theorem 1.3 enables us to consider the following nonlinearity

<!-- formula-not-decoded -->

̸

which satisfies ( g 0) -( g 3) . In view of Theorem 1.3 there is a ground state solution to (1.1) and

<!-- formula-not-decoded -->

We gain the following new biharmonic logarithmic Sobolev inequality .

THEOREM 1.4. For any u ∈ D 2 , 2 ( R N ) such that ∫ R N | u | 2 dx = 1 , there holds

<!-- formula-not-decoded -->

and

Moreover the equality in (1.7) holds provided that u = u 0 / ‖ u 0 ‖ L 2 ( R N ) and u 0 is a ground state solution to (1.1) . If the equality in (1.7) holds for u , then there are uniquely determined λ &gt; 0 and r &gt; 0 such that u 0 := λu ( r · ) ∈ M and u 0 is a ground state solution to (1.1) .

<!-- formula-not-decoded -->

Recall that the classical logarithmic Sobolev inequality given in [ 26 ]:

which is equivalent to the Gross inequality [ 13 ], cf. [ 14 ]. Recall that the optimality of (1.8) and the characterization of minimizers have been already proved by Carlen [ 8 ] in the context of the Gross inequality as well as by del Pino and Dolbeault [ 9 , 10 ] for the interpolated Gagliardo-Nirenberg inequalities and the L p -Sobolev logarithmic inequality. A generalization of the optimal Gross inequality in Orlicz spaces is given by Adams [ 1 ]. However, to the best of our knowledge, the logarithmic Sobolev inequality for higher order operators have not been obtained in the literature so far and (1.8) seems to be the first one for the biharmonic Laplacian. Note that, in contrast to (1.8) and the Laplacian problem involving (1.6), we do not know ground state solutions to (1.1) explicitly. Hence the exact computation of C N,log remains an open question.

<!-- formula-not-decoded -->

The paper is organized as follows. In Section 2 we prove Theorem 1.1 and in Section 3 we obtain the Pohožaev-type result. The main result of Section 4 is a general variant of Lion's lemma (Lemma 4.1) in D 2 , 2 ( R N ) , which is crucial for the proof of Theroem 1.3 given in Section 5. The last Section 6 is devoted to the biharmonic logarithmic Sobolev inequality.

## 2. Regularity theory and proof of Theorem 1.1

Let N , k ∈ N and 1 ≤ p &lt; ∞ with N &gt; kp . We define D k,p ( R N ) as a completion of the space C ∞ 0 ( R N ) with respect to the norm

Hence

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

and

<!-- formula-not-decoded -->

We fix an open set Ω ⊂ R N . We recall that by the standard approach based on mollifiers and the Calderon-Zygmund L p -estimates for higher order elliptic operators [ 22 , (2.6)] we have the following lemma.

LEMMA 2.1. Let 1 &lt; p &lt; ∞ and k be a positive integer. If w ∈ L p loc (Ω) and ∆ k w ∈ L p loc (Ω) , then w ∈ W 2 k,p loc (Ω) .

Suppose that u ∈ W 2 , 2 loc (Ω) is a weak solution to (1.1), where g satisfies (1.2). Clearly u ∈ L 2 ∗∗ loc (Ω) . Fix U ⊂⊂ Ω . Since 2 N N +4 &lt; N 4 and 2 N N +4 = 2 ∗∗ N -4 N +4 , by the Hölder inequality

for some constant c &gt; 0 . Then, by the distributional equality

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

and Lemma 2.1, we infer that u ∈ W 4 , 2 N N +4 loc (Ω) .

Now the crucial step is the following lemma.

LEMMA 2.2. Let p ≥ 2 N N +4 and u ∈ W 4 ,p loc (Ω) be a weak solution to (1.1) , where g satisfies (1.2) . Then

<!-- formula-not-decoded -->

PROOF. If 4 p ≥ N , then the conclusion follows immediately by the Sobolev embedding W 4 ,p loc (Ω) ⊂ L q loc (Ω) , q ≥ 1 . Thus, we can clearly assume that 4 p &lt; N . Let us define

̸

<!-- formula-not-decoded -->

and observe that g ( x, u ) = ˜ a ( x ) u + b ( x ) and ˜ a, b ∈ L N/ 4 loc (Ω) .

Let U be an arbitrary open bounded subset of Ω such that U ⊂ U ⊂ Ω . We find an open bounded V with C ∞ -smooth boundary such that U ⊂ V ⊂ V ⊂ Ω . Indeed, let ξ ∈ C ∞ 0 (Ω) be a smooth cut-off function such that ξ ≡ 1 on U and 0 ≤ ξ ≤ 1 . By Sard's theorem, there is a regular value c ∈ (0 , 1) . Then V = ξ -1 (( c, 1]) is an open bounded subset with the smooth boundary ∂V = ξ -1 ( { c } ) satisfying U ⊂ V ⊂ V ⊂ Ω .

Now take η ∈ C ∞ 0 ( V ) such that η = 1 on U and 0 ≤ η ≤ 1 . We restrict our problem to V . By the assumption u ∈ W 4 ,p ( V ) is a distributional solution of

<!-- formula-not-decoded -->

and ˜ a, b ∈ L N/ 4 ( V ) . We define

<!-- formula-not-decoded -->

Certainly, we have v ∈ W 4 ,p ( V ) ⊂ H 2 ( V ) and v ∈ H 1 0 ( V ) , since supp η ⊂⊂ V . Standard calculations yield

<!-- formula-not-decoded -->

Observe that u ∈ W 4 ,p ( V ) ⊂ W 3 ,p ∗ ( V ) , p ∗ = Np N -p and η ∈ C ∞ 0 ( V ) imply that

<!-- formula-not-decoded -->

for some constant c ( η ) &gt; 0 .

In view of [ 25 , Lemma B.2], for every ε &gt; 0 there are q ε ∈ L N/ 4 ( V ) and ̂ f ε ∈ L ∞ ( V ) such that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

By (2.4), (2.3) and (2.6) we get

<!-- formula-not-decoded -->

where

(2.9) f ε := ̂ f ε + b ( x ) η ∈ L N 4 ( V ) . We recall some needed regularity results from [ 2 ] (see also [ 12 , Thm 2.20]), for all 1 &lt; q &lt; ∞ , ¯ g ∈ L q ( V ) , there exists a unique strong solution u ∈ W 4 ,q ( V ) to the problem

satisfying

<!-- formula-not-decoded -->

‖

u

‖

W

4

,q

(

V

)

≤

c

q

‖

¯

g

‖

L

q

(

V

)

,

where c q &gt; 0 depends only on N , q and V . Denote by T q the linear operator g ↦→ u considered as an operator from L q ( V ) to W 4 ,q ( V ) and rewrite the above inequality as

<!-- formula-not-decoded -->

Obviously, T q is the L q -inverse of the bilaplacian ( -∆) 2 considered with the Navier boundary conditions u = ∆ u = 0 on ∂V .

Now we can rephrase (2.8) in the language of operators

<!-- formula-not-decoded -->

where A ε,q v := T q ( q ε v ) and h ε,q := T q ( f ε + K ( u )) .

We consider two cases separately.

to obtain

<!-- formula-not-decoded -->

In view of (2.13), (2.14) and (2.7) we gain

<!-- formula-not-decoded -->

We choose ε := (2 c Sobolev c p ∗ ) -1 to deduce

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Then ( I -A ε,p ∗ ) is invertible on the space L Np N -5 p ( V ) with the norm bounded by 2 and by (2.11)

<!-- formula-not-decoded -->

so by the above and by (2.12)

<!-- formula-not-decoded -->

Hence v ∈ L Np N -5 p ( V ) and, since u = v on U ⊂ Ω and U is arbitrary, we finally get u ∈ L Np N -5 p loc (Ω) as claimed. This finishes the proof of Case I.

<!-- formula-not-decoded -->

We proceed similarly as in Case I. Fix any Np N -4 p ≤ q &lt; ∞ and define r := Nq N +4 q . Then we have 1 &lt; r &lt; N 4 ≤ Np N -p . We employ the Sobolev embedding W 4 ,r ( V ) ⊂ L q ( V ) , (2.10), (2.9) and (2.5) to

## Case I: 5 p &lt; N .

In what follows we take q = p ∗ . By the Sobolev embedding W 4 ,p ∗ ( V ) ⊂ L Np N -5 p ( V ) , (2.10), (2.9) and (2.5), we have

<!-- formula-not-decoded -->

where c &gt; 0 is some constant. We estimate the norm of the linear operator A ε,p ∗ : L Np N -5 p ( V ) → L Np N -5 p ( V ) applying the Sobolev embedding W 4 ,p ∗ ( V ) ⊂ L Np N -5 p ( V ) and (2.10)

<!-- formula-not-decoded -->

We use the Hölder inequality with the exponents

<!-- formula-not-decoded -->

estimate

<!-- formula-not-decoded -->

for some constant c &gt; 0 . We bound the norm of A ε,r : L q ( V ) → L q ( V ) by exploiting the Sobolev embedding W 4 ,r ( V ) ⊂ L q ( V ) and (2.10)

<!-- formula-not-decoded -->

We use Hölder's inequality with exponents

and (2.7) to obtain

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

We choose ε = (2 c Sobolev c r ) -1 and from (2.18), (2.19) deduce that

<!-- formula-not-decoded -->

As in the last part of Case I, we then show that v ∈ L q ( V ) . This implies that u ∈ L q ( U ) and, since U ⊂ Ω and q ≥ Np N -4 p were arbitrary, the proof of Case II is completed. □

Proof of Theorem 1.1 . Let u ∈ W 2 , 2 loc (Ω) be a weak solution to (1.1). Then u ∈ W 4 , 2 N N +4 loc (Ω) . We show that u ∈ L q loc (Ω) , for every q ≥ 1 . If N = 5 or N = 6 , then, by Lemma 2.2, u ∈ L q loc (Ω) , for every q ≥ 1 , and we are done. If N &gt; 6 , then we define p 1 := 2 N N +4 , 5 p 1 &lt; N , and we use Lemma 2.2 to obtain u ∈ L Np 1 N -5 p 1 loc (Ω) . Since Np 1 N -5 p 1 = 2 N N -6 ,

<!-- formula-not-decoded -->

Fix U ⊂⊂ Ω . Observe that p 2 N +2 8 = N 4 and by the Hölder inequality

for some constant c &gt; 0 . Therefore we get ∆ 2 u = g ( x, u ) ∈ L p 2 loc (Ω) . Since u ∈ W 4 ,p 1 loc (Ω) ⊂ L p 2 loc (Ω) , we use Lemma 2.1 to get u ∈ W 4 ,p 2 loc ( R N ) . Let K be the largest natural number less than N -4 2 . We continue applying Lemma 2.2 in this fashion and get a finite sequence ( p k ) K k =1 such that for k = 1 , ..., K

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

By the definition of K , we get 5 p K &lt; N , Np K N -5 p K ≥ N and u ∈ L Np K N -5 p K loc (Ω) . Finally, by Lemma 2.2 we obtain that u ∈ L q loc (Ω) , for every q ≥ 1 . Since ∆ 2 u = g ( x, u ) ∈ L q loc (Ω) , for every 1 ≤ q &lt; ∞ , by Lemma 2.1, u ∈ W 4 ,q loc (Ω) , q ≥ 1 , so by the Sobolev embedding u ∈ C 3 ,α loc (Ω) , for every 0 &lt; α &lt; 1 . □

## 3. Pohožaev identity

Proof of Theorem 1.2 . One can find ϕ ∈ C ∞ ( R ) satisfying ϕ | ( -∞ , 1] ≡ 1 , ϕ | [2 , ∞ ) ≡ 0 and 0 ≤ ϕ ≤ 1 . For every n ≥ 1 , we define ϕ n ∈ C ∞ 0 ( R N ) by ϕ n ( x ) := ϕ ( | x | 2 n 2 ) .

By Theorem 1.1, we may assume that u ∈ C 3 ,α loc ( R N ) ∩ W 4 ,q loc ( R N ) , 0 &lt; α &lt; 1 , 1 ≤ q &lt; ∞ , so

<!-- formula-not-decoded -->

Thus, for a.e. x ∈ R N and for every n , we obtain

(3.1)

The following identities hold

<!-- formula-not-decoded -->

and

<!-- formula-not-decoded -->

We transform the rightmost term of the above equation

<!-- formula-not-decoded -->

Finally, we rewrite the second term of the above line as follows

Putting the above identities into (3.1) we get

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

or, equivalently,

<!-- formula-not-decoded -->

Fix n ≥ 1 and take R &gt; 0 such that supp ϕ n ⊂ B R . By the divergence theorem, we obtain

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Note that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

We return to (3.3) and pass to the limit as n →∞ to obtain

where we used Lebesgue's dominated convergence theorem and the properties of ϕ n . The proof is completed. □

<!-- formula-not-decoded -->

## 4. Lions lemma

We prove a biharmonic variant of Lion's lemma, cf. [ 15 , 16 ], [ 20 , Section 2].

LEMMA 4.1. Suppose that ( u n ) is bounded in D 2 , 2 ( R N ) and for some r &gt; 0

<!-- formula-not-decoded -->

Then

for every continuous Ψ : R → R satisfying

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

We prove the following result, which implies the variant of Lions's lemma in D 2 , 2 ( R N ) .

LEMMA 4.2. Suppose that ( u n ) ⊂ D 2 , 2 ( R N ) is bounded. Then u n ( · + y n ) ⇀ 0 in D 2 , 2 ( R N ) for any ( y n ) ⊂ Z N if and only if

for any continuous Ψ : R → R satisfying (4.2) .

<!-- formula-not-decoded -->

PROOF. Let ( u n ) be a sequence in D 2 , 2 ( R N ) be such that u n ( · + y n ) ⇀ 0 in D 2 , 2 ( R N ) for every ( y n ) ⊂ Z N . Take any ε &gt; 0 and 2 ∗ &lt; p &lt; 2 ∗∗ and suppose that Ψ satisfies (4.2). Then we find 0 &lt; δ &lt; M and c ( ε ) &gt; 0 such that

<!-- formula-not-decoded -->

Let us define ( w n ) by

<!-- formula-not-decoded -->

We are about to show that ( w n ) is bounded in W 1 , 2 ∗ ( R N ) . First of all, we have

By the absolute continuous characterization (see §1.1.3 in [ 18 ]), we infer that each u n is absolutely continuous on almost every line parallel to the 0 x i -axis, for i = 1 , . . . , N . Thus the same holds for each w n , since w n = F ( u n ) , where F ( t ) = min { δ 1 -2 ∗∗ / 2 ∗ | t | 2 ∗∗ / 2 ∗ , | t |} is a globally Lipschitz function. Moreover, for every i = 1 , . . . , N , we have

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Thus

∣ ∣ By (4.3), (4.4) (again using an absolute continuous characterization on lines from §1.1.3 [ 18 ]) and the fact that ( u n ) is bounded in D 2 , 2 ( R N ) , we conclude that ( w n ) is bounded in W 1 , 2 ∗ ( R N ) .

<!-- formula-not-decoded -->

Let Ω = (0 , 1) N and y ∈ R N be arbitrary. Then, by the Sobolev inequality one has

where C &gt; 0 is a constant from the Sobolev inequality. Then we sum the inequalities over y ∈ Z N and get

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Let us take ( y n ) ⊂ Z N such that

<!-- formula-not-decoded -->

for any n ≥ 1 . By the assumption u n ( · + y n ) ⇀ 0 in D 2 , 2 ( R N ) and passing to a subsequence we obtain u n ( · + y n ) → 0 in L p (Ω) .

<!-- formula-not-decoded -->

̸

<!-- formula-not-decoded -->

Since | w n ( x ) | ≤ | u n ( x ) | , we infer that w n ( · + y n ) → 0 in L p (Ω) . Therefore

and since ε &gt; 0 is arbitrary, the assertion follows.

On the other hand, suppose that u n ( · + y n ) does not converge to 0 in D 2 , 2 ( R N ) , for some ( y n ) in Z N , and Ψ( u n ) → 0 in L 1 ( R N ) . We may assume that u n ( · + y n ) → u 0 = 0 in L p (Ω) for some bounded domain Ω ⊂ R N and 1 &lt; p &lt; 2 ∗∗ . Take any ε &gt; 0 , q &gt; 2 ∗∗ and let us define Ψ( s ) := min {| s | p , ε p -q | s | q } for s ∈ R . Then

̸

Thus we get u n ( · + y n ) → 0 in L p (Ω) and this contradicts u 0 = 0 .

̸

□

Proof of Lemma 4.1 . Suppose that there is ( y n ) ⊂ Z N such that u n ( · + y n ) does not converge weakly to 0 in D 2 , 2 ( R N ) . Since u n ( · + y n ) is bounded, there is u 0 = 0 such that, up to a subsequence,

<!-- formula-not-decoded -->

̸

<!-- formula-not-decoded -->

as n → ∞ . We find y ∈ R N such that u 0 χ B ( y,r ) = 0 in L 2 ( B ( y, r )) . Observe that, passing to a subsequence, we may assume that u n ( · + y n ) → u 0 in L 2 ( B ( y, r )) . Then, in view of (4.1)

̸

as n →∞ , which contradicts the fact u n ( · + y n ) → u 0 = 0 in L 2 ( B ( y, r )) . Therefore u n ( · + y n ) ⇀ 0 in D 2 , 2 ( R N ) for any ( y n ) ⊂ Z N and by Lemma 4.2 we conclude. □

## 5. Proof of Theorem 1.3

In this section we adapt a variational approach from [ 20 , Section 3] for the bi-Laplacian. Let

Notice that G + , G -≥ 0 and G = G + -G -.

<!-- formula-not-decoded -->

First, we sketch our approach with an approximation J ε of J and present some auxiliary lemmas. The proof of Theorem 1.3 is postponed to the end of the section. Let

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Notice that G -( s ) = ∫ s 0 g -( t ) dt ≥ 0 , for s ∈ R . In view of (g1) and (g3), there is some c &gt; 0 such that for every s ∈ R

so G + ( u ) ∈ L 1 ( R N ) whenever u ∈ D 2 , 2 ( R N ) ⊂ L 2 ∗∗ ( R N ) . On the other hand, G -( u ) may not be integrable, for u ∈ D 2 , 2 ( R N ) , unless G -( u ) ≤ c | u | 2 ∗∗ for some c &gt; 0 . To overcome this problem, for

ε ∈ (0 , 1) , we define ϕ ε : R → [0 , 1] by

We introduce a new functional

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

This implies that G ε -( s ) ≤ c ( ε ) | s | 2 ∗∗ for any s ∈ R and some constant c ( ε ) &gt; 0 depending on ε &gt; 0 . Hence, for ε ∈ (0 , 1) , J ε is well-defined on D 2 , 2 ( R N ) , continuous and J ′ ε ( u )( v ) exists for any u ∈ D 2 , 2 ( R N ) and v ∈ C ∞ 0 ( R N ) . Therefore, we say that u is a critical point of J ε provided that J ′ ε ( u )( v ) = 0 for any v ∈ C ∞ 0 ( R N ) .

̸

We define, for ε ∈ (0 , 1) ,

<!-- formula-not-decoded -->

and introduce the map m P ε : P ε →M ε given by

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

where

We check that m P ε is well-defined. If u ∈ P ε , then

<!-- formula-not-decoded -->

LEMMA 5.1. For every δ &gt; 0 there is c δ &gt; 0 such that

<!-- formula-not-decoded -->

for all u, v ∈ R .

□

PROOF. First, we show that for every δ &gt; 0 there is c ( δ ) &gt; 0 such that

<!-- formula-not-decoded -->

Fix δ &gt; 0 and u , v ∈ R . By the mean value theorem, there is θ ∈ (0 , 1) such that

<!-- formula-not-decoded -->

where we used (5.3). We exploit the Young inequality with δ/c 1 ( ε )

<!-- formula-not-decoded -->

to obtain

<!-- formula-not-decoded -->

what proves the assertion.

Now, we show that for every δ &gt; 0 there is c ( δ ) &gt; 0 such that

<!-- formula-not-decoded -->

Fix δ &gt; 0 and u , v ∈ R . By (g1) and (g3), there are 0 &lt; η &lt; M such that

<!-- formula-not-decoded -->

if | s | &lt; η or | s | &gt; M . We consider four cases.

Case I: | u + v | &lt; η or | u + v | &gt; M .

We use the fact that G + ≥ 0 and obtain

what proves the assertion.

<!-- formula-not-decoded -->

Case II: η ≤ | u + v | ≤ M and | v | &gt; M .

There is c &gt; 0 such that G + ( s ) ≤ c | s | 2 ∗∗ , for every s ∈ R , so

<!-- formula-not-decoded -->

and we are done.

Case III: η ≤ | u + v | ≤ M and η/ 2 ≤ | v | ≤ M .

The set C := { ( u, v ) ∈ R 2 | η ≤ | u + v | ≤ M and η/ 2 ≤ | v | ≤ M } is compact and the function h : C → R , given by h ( u, v ) := G + ( u + v ) -G + ( u ) -δ | u | 2 | v | 2 ∗∗ , is continuous. Thus, there is c ( δ ) &gt; 0 such that

max ( u,v ) ∈ C h ( u, v ) ≤ c ( δ ) and we are done.

Case IV: η ≤ | u + v | ≤ M and | v | &lt; η/ 2 .

By the continuity of g + and by (g0), there is c ( η ) such that

<!-- formula-not-decoded -->

By the mean value theorem, there is θ ∈ (0 , 1) such that

<!-- formula-not-decoded -->

Notice that | u + θv | ≥ | u + v | -(1 -θ ) | v | &gt; η -η/ 2 = η/ 2 , so combining the above we obtain

<!-- formula-not-decoded -->

We then proceed as in the first part of the proof.

∗∗

Finally, we use the above results to deduce

<!-- formula-not-decoded -->

LEMMA 5.2. Suppose that ( u n ) ⊂ M ε , J ε ( u n ) → c ε and

̸

for some ˜ u ∈ D 2 , 2 ( R N ) . Then u n → ˜ u , ˜ u is a critical point of J ε and J ε ( ˜ u ) = c ε . PROOF. It follows, by Lemma 5.1, that for every δ &gt; 0 theres is c ( δ ) &gt; 0 such that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Thus taking any v ∈ C ∞ 0 ( R N ) and t ∈ R we observe that ( G ε ( u n + tv ) -G ε ( u n )) is uniformly integrable and tight. In view of Vitali's convergence theorem we have

Since each u n ∈ M ε , we get

<!-- formula-not-decoded -->

so

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Combining the above we have

By (5.5) and Lemma 5.1, u n + tv ∈ P ε for sufficiently large n and sufficiently small | t | . Thus and by (5.6), for sufficiently small | t | , we have

and, consequently, by the Lebesgue dominated convergence theorem (5.7)

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Raising both sides to the 4 /N -power yields

<!-- formula-not-decoded -->

Assumptions u n ∈ M ε and J ε ( u n ) → c ε imply that

<!-- formula-not-decoded -->

For all n and t , we have

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Hence, by (5.8) and since u n ∈ M ε , for t &gt; 0 ,

Letting n →∞ , by (5.6), (5.5) and (5.9), we deduce that, for sufficiently small t &gt; 0 ,

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Since v ∈ C ∞ 0 ( R N ) was arbitrary we infer that ˜ u is a critical point of J ε . We use the Pohožaev identity Theorem 1.2 to the equation ∆ 2 u = g ε ( u ) with G ε ∈ L 1 ( R N ) , to deduce that u ∈ M ε , what leads to

PROOF OF THEOREM 1.3. Take a minimizing sequence ( u n ) in M ε of J ε , i.e., J ε ( u n ) → c ε . Since u n ∈ M ε , n ≥ 1 , we have

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

and so ( u n ) is bounded in D 2 , 2 ( R N ) . Moreover, we have

̸

By the assumption G + satisfies (4.2), so (4.1) is not satisfied. Passing to a subsequence, we may choose ( y n ) in R N and 0 = u ε ∈ D 2 , 2 ( R N ) such that

<!-- formula-not-decoded -->

as n →∞ . In view of Lemma 5.2, u ε ∈ M ε is a critical point of J ε at the level c ε .

<!-- formula-not-decoded -->

Choose ε n → 0 + . Fix an arbitrary u ∈ M . Since G ε ( s ) ≥ G ( s ) , for all s ∈ R and ε ∈ (0 , 1) , we deduce that

so m P εn ( u ) ∈ M ε n is well-defined. We have

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Thus J ε n ( u ε n ) ≤ inf M J and

We have G ε ( s ) ≤ G 1 / 2 ( s ) , for all s ∈ R and ε ∈ (0 , 1 / 2) , so

and some calculations yield

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Therefore, we get

<!-- formula-not-decoded -->

̸

By (5.10), ( u ε n ) is bounded in D 2 , 2 ( R N ) and ∫ R N G + ( u ε n ) dx &gt; c &gt; 0 , for some constant c . In view of Lemma 4.1, (4.1) is not satisfied. Passing to a subsequence, there is ( y n ) in R N such that u ε n ( · + y n ) ⇀ u 0 = 0 and u ε n ( x + y n ) → u 0 ( x ) a.e. in R N . We write ˜ u n := u ε n ( · + y n ) for short. Since g -is continuous and g -(0) = 0 , one may check that, for every v ∈ C ∞ 0 ( R N ) ,

and

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

∣ ∣ χ {| ˜ u n | &gt;ε n } g -( ˜ u n ) v -g -( u 0 ) v ∣ ∣ → 0 a.e. in R N . Due to the estimate | g -( ˜ u n ) v | ≤ c ( 1 + | ˜ u n | 2 ∗∗ -1 ) | v | , the family { g -( ˜ u n ) v } is uniformly integrable (and tight because of the compact support). In view of Vitali's convergence theorem as n →∞ . Similarly, we obtain Gathering the above we deduce that

<!-- formula-not-decoded -->

Each ˜ u n is a critical point of J ε n , since so is u ε n (translation invariance), hence

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

i.e., u 0 is a weak solution to (1.1). By Lebesgue's dominated convergence theorem one may show that

as n →∞ , and, on the other hand,

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

namely, we have shown that G -( u 0 ) ∈ L 1 ( R N ) . By the Pohožaev identity, we infer that u 0 ∈ M . Lastly, we show that J ( u 0 ) = inf M J . We use the weak l.s.c. of the norm and (5.10) to find that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

## 6. Biharmonic logarithmic inequality

LEMMA 6.1. If u ∈ D 2 , 2 ( R N ) and ∫ R N | u | 2 dx = 1 , then

<!-- formula-not-decoded -->

PROOF. We rely on ideas from [ 4 ]. Let us define the Fourier transform u of u (whenever possible) as

If u ∈ D 2 , 2 ( R N ) and ∫ R N | u | 2 dx = 1 , then u ∈ H 2 ( R N ) and by the Plancharel theorem

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

By the Cauchy-Schwartz inequality we get

<!-- formula-not-decoded -->

Proof of Theorem 1.4 . Observe that the following inequality holds

and the assertion follows with the non-strict inequality. Recall that the equality in the Cauchy-Schwartz inequality holds if and only if | ξ | 2 ̂ u ( ξ ) = λ ̂ u ( ξ ) for some λ , what implies ̂ u = 0 . Hence the inequality in the statement is in fact strict. □

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

where

Indeed, it is enough to consider u ∈ D 2 , 2 ( R N ) such that ∫ R N | u | 2 log | u | dx &gt; 0 . We then obtain u ( r · ) ∈ M , where

Hence J ( u ( r · )) ≥ inf M J and we get (6.1).

Now note that (6.1) is equivalent to

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Assuming that ∫ R N | u | 2 dx = 1 , the maximum of the right hand side of (6.2) is attained at α = N -4 8 -∫ R N | u | 2 log | u | dx . Hence we get

that is

<!-- formula-not-decoded -->

and

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

thus (1.7) holds.

We show that the constant in (1.7) is optimal, i.e., there is u ∈ D 2 , 2 ( R N ) such that the equality holds. First of all, notice that if u 0 is a minimizer given by Theorem 1.3, then for u 0 we have the equality in (6.1):

<!-- formula-not-decoded -->

We use (6.1) for the family of functions e α ‖ u 0 ‖ L 2 u 0 ∈ D 2 , 2 ( R N ) , α ∈ R , to get

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

Note that

On the other hand, f attains maximum at α = log( ‖ u 0 ‖ L 2 ) in view of (6.4) and (6.3), thus

or, equivalently,

<!-- formula-not-decoded -->

where we used the fact that u 0 ∈ M . Therefore we obtain the equality in (1.7) for the function u 0 ‖ u 0 ‖ L 2 . Let us now suppose that

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

for some u ∈ D 2 , 2 ( R N ) such that ‖ u ‖ L 2 ( R N ) = 1 . Then

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

for α = N -4 8 -∫ R N | u | 2 log | u | dx and the equality in (6.1) holds for u 1 := e α u . Hence J ( u 0 ) = inf M J for

Let us sketch the proof that u 0 is a critical point of J . Firstly, note that, for every v ∈ C ∞ 0 ( R N ) , G ( u 0 + v ) ∈ L 1 ( R N ) , for G ( s ) := s 2 log | s | . Fix an arbitrary v ∈ C ∞ 0 ( R N ) . We use the fact that G is C 1 -smooth and the Lebesgue dominated convergence theorem to get

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

By the continuity, ∫ R N G ( u 0 + tv ) dx &gt; 0 , for sufficiently small | t | &gt; 0 , so ( u 0 + tv )( r · ) ∈ M , where

Hence

or, equivalently,

<!-- formula-not-decoded -->

We then proceed similarly as in the last part of the proof of Lemma 5.2 to conclude that

<!-- formula-not-decoded -->

which yields that u 0 is a critical point of J .

Finally, we show the estimate of the constant C N,log from Theorem 1.7. Observe that if u ∈ D 2 , 2 ( R N ) and ∫ R N | u | 2 dx = 1 , then u ∈ H 2 ( R N ) . In view of Lemma 6.1 and the logarithmic Sobolev inequality (1.8) we obtain

<!-- formula-not-decoded -->

## Acknowledgements

The authors were supported by the National Science Centre, Poland (Grant No. 2017/26/E/ST1/00817). J. Mederski was also partially supported by the Deutsche Forschungsgemeinschaft (DFG, German Research Foundation) - Project-ID 258734477 - SFB 1173 during the stay at Karlsruhe Institute of Technology.

## References

- [1] R. A. Adams, Sobolev spaces , Academic Press [A subsidiary of Harcourt Brace Jovanovich, Publishers], New York-London, 1975. Pure and Applied Mathematics, Vol. 65.
- [2] S. Agmon, A. Douglis, and L. Nirenberg, Estimates near the boundary for solutions of elliptic partial differential equations satisfying general boundary conditions. I , Comm. Pure Appl. Math. 12 (1959), 623-727.
- [3] S. S. Antman, Nonlinear problems of elasticity , 2nd ed., Applied Mathematical Sciences, vol. 107, Springer, New York, 2005.
- [4] J. Bellazzini, R. L. Frank, and N. Visciglia, Maximizers for Gagliardo-Nirenberg inequalities and related non-local problems , Math. Ann. 360 (2014), no. 3-4, 653-673.
- [5] H. Berestycki and P.-L. Lions, Nonlinear scalar field equations. I. Existence of a ground state , Arch. Rational Mech. Anal. 82 (1983), no. 4, 313-345.
- [6] H. Brézis and T. Kato, Remarks on the Schrödinger operator with singular complex potentials , J. Math. Pures Appl. (9) 58 (1979), no. 2, 137-151.
- [7] H. Brezis and E. H. Lieb, Minimum action solutions of some vector field equations , Comm. Math. Phys. 96 (1984), no. 1, 97-113.
- [8] E. A. Carlen, Superadditivity of Fisher's information and logarithmic Sobolev inequalities , J. Funct. Anal. 101 (1991), no. 1, 194-211. MR1132315
- [9] M. del Pino and J. Dolbeault, Best constants for Gagliardo-Nirenberg inequalities and applications to nonlinear diffusions , J. Math. Pures Appl. (9) 81 (2002), no. 9, 847-875.
- [10] M. del Pino and J. Dolbeault, The optimal Euclidean L p -Sobolev logarithmic inequality , J. Funct. Anal. 197 (2003), no. 1, 151-161.
- [11] G. Fibich, B. Ilan, and G. Papanicolaou, Self-focusing with fourth-order dispersion , SIAM J. Appl. Math. 62 (2002), no. 4, 1437-1462.
- [12] F. Gazzola, H.-C. Grunau, and G. Sweers, Polyharmonic boundary value problems , Lecture Notes in Mathematics, vol. 1991, Springer-Verlag, Berlin, 2010. Positivity preserving and nonlinear higher order elliptic equations in bounded domains.
- [13] L. Gross, Logarithmic Sobolev inequalities , Amer. J. Math. 97 (1975), no. 4, 1061-1083.
- [14] E. H. Lieb and M. Loss, Analysis , 2nd ed., Graduate Studies in Mathematics, vol. 14, American Mathematical Society, Providence, RI, 2001.
- [15] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. II , Ann. Inst. H. Poincaré Anal. Non Linéaire 1 (1984), no. 4, 223-283.
- [16] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. I , Ann. Inst. H. Poincaré Anal. Non Linéaire 1 (1984), no. 2, 109-145.
- [17] S. Mayboroda and V. Maz'ya, Regularity of solutions to the polyharmonic equation in general domains , Invent. Math. 196 (2014), no. 1, 1-68.
- [18] V. G. Maz'ja, Sobolev spaces , Springer Series in Soviet Mathematics, Springer-Verlag, Berlin, 1985. Translated from the Russian by T. O. Shaposhnikova.
- [19] J. Mederski, Nonradial solutions of nonlinear scalar field equations , Nonlinearity 33 (2020), no. 12, 6349-6380.
- [20] J. Mederski, General class of optimal Sobolev inequalities and nonlinear scalar field equations , J. Differential Equations 281 (2021), 411-441.

- [21] V. V. Meleshko, Selected topics in the history of the two-dimensional biharmonic problem , Appl. Mech. Rev. 56 (2003), 33-85.
- [22] L. Nirenberg, Estimates and existence of solutions of elliptic equations , Comm. Pure Appl. Math. 9 (1956), 509-529.
- [23] P. Pucci and J. Serrin, A general variational identity , Indiana Univ. Math. J. 35 (1986), no. 3, 681-703.
- [24] A. P. S. Selvadurai, Partial differential equations in mechanics. 2 , Springer-Verlag, Berlin, 2000. The biharmonic equation, Poisson's equation.
- [25] R. C. A. M. Van der Vorst, Best constant for the embedding of the space H 2 ∩ H 1 0 (Ω) into L 2 N/ ( N -4) (Ω) , Differential Integral Equations 6 (1993), no. 2, 259-276.
- [26] F. B. Weissler, Logarithmic Sobolev inequalities for the heat-diffusion semigroup , Trans. Am. Math. Soc. 237 (1978), 255269.

## (J. Mederski)

INSTITUTE OF MATHEMATICS,

POLISH ACADEMY OF SCIENCES,

UL. ´ SNIADECKICH 8, 00-656 WARSAW, POLAND AND

DEPARTMENT OF MATHEMATICS,

KARLSRUHE INSTITUTE OF TECHNOLOGY (KIT),

D-76128 KARLSRUHE, GERMANY

Email address :

jmederski@impan.pl

## (J. Siemianowski)

FACULTY OF MATHEMATICS AND COMPUTER SCIENCES, NICOLAUS COPERNICUS UNIVERSITY IN TORU ´ N UL. GAGARINA 11, 87-100 TORU ´ N, POLAND

AND

INSTITUTE OF MATHEMATICS, POLISH ACADEMY OF SCIENCES, UL. ´ SNIADECKICH 8, 00-656 WARSAW, POLAND

Email address : jsiem@mat.umk.pl