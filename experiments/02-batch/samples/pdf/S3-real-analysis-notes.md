                                                                      Biharmonic nonlinear scalar field equations




arXiv:2107.07320v1 [math.AP] 15 Jul 2021
                                                                                Jarosław Mederski and Jakub Siemianowski

                                                    A BSTRACT. We prove a Brezis-Kato-type regularity result for weak solutions to the biharmonic nonlinear
                                                    equation
                                                                                              ∆2 u = g(x, u)       in RN
                                                    with a Carathéodory function g : RN × R → R, N ≥ 5. The regularity results give rise to the existence
                                                    of ground state solutions provided that g has a general subcritical growth at infinity. We also conceive a new
                                                    biharmonic logarithmic Sobolev inequality
                                                              Z                              Z                                          Z
                                                                                       N
                                                                    |u|2 log |u| dx ≤    log C       |∆u|2 dx , for u ∈ H 2 (RN ),            u2 dx = 1,
                                                                RN                     8          RN                                       RN
                                                                                   2
                                                                                  2
                                                    for a constant 0 < C < πeN         and we characterize its minimizers.




                                                                                                 1. Introduction
                                               The study of higher-order differential elliptic operators is important, e.g. in nonlinear elasticity [3], low
                                           Reynolds number hydrodynamics, in structural engineering [21, 24] as well as in nonlinear optics [11], and
                                           has attracted attention from the mathematical point of view [12]. The methods developed for the second
                                           order problem, e.g. involving the Laplacian −∆, may no longer be available. For instance, it is the well-
                                           known that the bi-Laplacian (−∆)2 = ∆2 cannot be studied by means of some classical methods such
                                           as maximum principles, Polya-Szegő inequalities, or even if (∆u)2 ∈ L1 (RN ), then it is possible that
                                           ∆|u| ∈/ L1loc (RN ).
                                               The first aim is of this work is to establish a regularity result in the spirit of Brezis-Kato [6] of weak
                                           solutions to
                                           (1.1)                                           ∆2 u = g(x, u),        x ∈ Ω,
                                           where Ω ⊂ RN is a domain, N ≥ 2 and g : Ω × R → R is a Carathéodory function. If we suppose that Ω is
                                           bounded, then there is an extensive literature devoted to this problem. Namely, recall that if g(x, u) = f (x),
                                           then Agmon, Douglis, Nirenberg [2] showed that for 1 < q < ∞, f ∈ Lq (Ω), there exists a unique strong
                                           solution u ∈ W02,2 (Ω)∩W 4,q (Ω) to (1.1) provided that ∂Ω ∈ C 4 see also [12, Corollary 2.21] and references
                                           therein. Recently Mayboroda and Maz’ya [17] showed L∞ -estimates of u (resp. ∇u), where f ∈ C0∞ (Ω),
                                           Ω is an arbitrary bounded domain and N = 4, 5 (resp. N = 2, 3). To the best of our knowledge, a variant
                                           of Brezis-Kato result [6] for (1.1) is known only on a bounded domain in a particular case. Namely, Van
                                           der Vorst [25] showed that, if N ≥ 5, g(x, u) = a(x)u and a(x) ∈ LN/4 (Ω), then any weak solution
                                           u ∈ W01,2 (Ω) ∩ W 2,2 (Ω) to (1.1) satisfies u ∈ Lq (Ω) for all 1 ≤ q < ∞. This result is suitable to show
                                           the regularity for the biharmonic equation with the nonlinearities of the special form g(x, u) = f (u)u cf.
                                           [25, Lemma B3]. In this paper we give a full answer to the problem on an arbitrary domain and for general
                                           g with the adequate Brezis-Kato growth as we shall see below.
                                                 2000 Mathematics Subject Classification. 35J91,35J20.
                                                 Key words and phrases. Nonlinear scalar field equation, Brezis-Kato reqularity, biharmonic logarithmic Sobolev inequality,
                                           critical point theory, Pohozaev manifold.
                                                                                                          1
2                                       J. MEDERSKI AND J. SIEMIANOWSKI

    From now on we assume that Ω ⊂ RN possibly unbounded domain and N ≥ 5. Inspired by [6], we
impose on g the following growth assumption:
                                                                               N/4
(1.2)       |g(x, s)| ≤ a(x) 1 + |s| , for s ∈ R and a.e. x ∈ Ω, where 0 ≤ a ∈ Lloc (Ω).
    The first main result reads as follows.
                                 2,2
    T HEOREM 1.1. Let u ∈ Wloc       (Ω) be a weak solution to (1.1), where g satisfies (1.2). Then u ∈
 3,α         4,q
Cloc (Ω) ∩ Wloc (Ω), for any 0 < α < 1 and 1 ≤ q < ∞.
     It is worth mentioning that in proof of Theorem 1.1 we can no longer apply classical techniques for
Laplacian, e.g. due to Brezis and Kato [6], or Brezis and Lieb [7, Theorem 2.3], since ∆|u| may not be
                         2,2
well-defined for u ∈ Wloc    (Ω). Moreover, the Moser iteration technique does not seem to be applicable
straightforwardly for g.
     We shall present some consequences of Theorem 1.1 in Ω = RN . Let us define D 2,2 (RN ) as a comple-
                                                                 P                        1
                                                                                            2
tion of the space C0∞ (RN ) with respect to the norm kukD2,2 :=      |α|=2 k∂ α uk2
                                                                                  L2 (RN )
                                                                                              . By the use of
the Fourier transform and the Plancharel theorem we find a constant c > 0 such that, for u ∈ C0∞ (RN ),
                                1
                                  kukD2,2 (RN ) ≤ k∆ukL2 (RN ) ≤ ckukD2,2 (RN ) .
                                c
Therefore, the norms kuk := k∆ukL2 (RN ) and kukD2,2 (RN ) are equivalent on D 2,2 (RN ). Moreover,
D 2,2 (RN ) is a Hilbert space with the inner product
                                         Z
                              hu, vi :=      ∆u∆v dx       for u, v ∈ D 2,2 (RN )
                                    RN
         2,2 N
and u ∈ D (R ) is a weak solution to (1.1) provided that
                                        Z
                             hu, vi =            g(x, u)v   for any v ∈ C0∞ (RN ).
                                            RN
    As usually expected, the following general Pohožaev-type result holds, cf. [23].
    T HEOREM 1.2. Let u ∈ D 2,2 (RN ) be a weak solution to (1.1), where g satisfies (1.2). Then
                Z                        Z                         Z
                                    2N                         2
(1.3)                |∆u|2 dx =               G(x, u) dx +              x · ∂x G(x, u) dx.
                  RN               N − 4 RN                 N − 4 RN
                                                                   Rs
provided that G(x, u), x · ∂x G(x, u) ∈ L1 (RN ), where G(x, s) := 0 g(x, t) dt, x ∈ RN , t ∈ R.
    We demonstrate that the Brezis-Kato result for biharmonic Laplacean as well as Theorem 1.2 open
the way to study the existence of solutions and their regularity for (1.1). Indeed, let us assume that g is
independent of x and the following condition holds:
                                                                   
    (g0) there is a constant c > 0 such that |g(s)| ≤ c 1 + |s|2 −1 for s ∈ R,
                                                                ∗∗


                                                                    N/4
where 2∗∗ := N2N                                                        N             2 (RN ) and in view
                                                                                        ∗∗
                   −4 . Then a(x) := g(u(x))/(1 + |u(x)|) ∈ Lloc (R ) for u ∈ L
                                                                               3,α            4,q
of Theorem 1.1, weak solutions to the semilinear problem (1.1) belong to Cloc (RN ) ∩ Wloc        (RN ). We
introduce the energy functional
                                               Z            Z
                                            1           2
(1.4)                               J(u) :=        |∆u| −       G(u) dx,
                                            2 RN             RN
                Rs
where G(s) = 0 g(t) dt. Next, we show the existence of weak solutions to (1.1) under growth assumption
at 0 and at infinity inspired by a seminal paper due to Berestycki and Lions [5] (cf. [19, 20]). We assume
that g is continuous, g(0) = 0 and (g0) holds. Let
                                          (R
                                              s
                                                max{g(t), 0} dt    for s ≥ 0,
                                G+ (s) := R00
                                             s max{−g(t), 0} dt for s < 0,
                                BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                    3

and g+ (s) = G′+ (s). Suppose in addition, that and the following conditions are satisfied:
      (g1) lims→0 G+ (s)/|s|2 = 0,
                               ∗∗


      (g2) there exists ξ0 > 0 such that G(ξ0 ) > 0,
      (g3) lim|s|→∞ G+ (s)/|s|2 = 0.
                                 ∗∗


We introduce the Pohožaev manifold
                          n                 Z                                     Z           o
                                  2,2 N                               2      ∗∗
(1.5)               M := u ∈ D (R ) \ {0} :                       |∆u| = 2             G(u) dx ,
                                                             RN                   RN
and in view of Theorem 1.2, M contains all nontrivial solutions. The existence result reads as follows.
    T HEOREM 1.3. Let (g0)–(g3) be satisfied. Then inf M J > 0 and there is a ground state solution u0 ∈
                                                                                  3,α           4,q
D (RN ) to (1.1), i.e. u0 ∈ M solves (1.1) and J(u0 ) = inf M J. Moreover u0 ∈ Cloc
 2,2                                                                                  (RN ) ∩ Wloc  (RN ),
for any 0 < α < 1 and 1 ≤ q < ∞.
      Theorem 1.3 enables us to consider the following nonlinearity
(1.6)                               G(s) = s2 log |s| for s 6= 0, and G(0) = 0
which satisfies (g0)–(g3). In view of Theorem 1.3 there is a ground state solution to (1.1) and
                                              1    1 − N−4 4
                                                                        4
                                CN,log := 2∗∗    − ∗∗          (inf J) N−4 .
                                               2 2               M

We gain the following new biharmonic logarithmic Sobolev inequality.
                                                     R
    T HEOREM 1.4. For any u ∈ D 2,2 (RN ) such that RN |u|2 dx = 1, there holds
                                         (N −4)/N Z              ! Z
                 N               8e
(1.7)               log                                        2
                                                          |∆u| dx ≥           |u|2 log |u| dx
                 8         CN,log (N − 4)             R N                 R N


and
                                                         (N −4)/N        2 2
                                               8e
                                                                      <          .
                                         CN,log (N − 4)                    πeN
Moreover the equality in (1.7) holds provided that u = u0 /ku0 kL2 (RN ) and u0 is a ground state solution
to (1.1). If the equality in (1.7) holds for u, then there are uniquely determined λ > 0 and r > 0 such that
u0 := λu(r·) ∈ M and u0 is a ground state solution to (1.1).
    Recall that the classical logarithmic Sobolev inequality given in [26]:
                  2 Z                  Z                                        Z
          N
(1.8)        log                    2
                               |∇u| dx ≥            2                       1 N
                                                 |u| log(|u|) dx, for u ∈ H (R ),       |u|2 dx = 1,
          4        πeN RN                    R N                                    R N

which is equivalent to the Gross inequality [13], cf. [14]. Recall that the optimality of (1.8) and the char-
acterization of minimizers have been already proved by Carlen [8] in the context of the Gross inequality as
well as by del Pino and Dolbeault [9, 10] for the interpolated Gagliardo–Nirenberg inequalities and the Lp -
Sobolev logarithmic inequality. A generalization of the optimal Gross inequality in Orlicz spaces is given
by Adams [1]. However, to the best of our knowledge, the logarithmic Sobolev inequality for higher order
operators have not been obtained in the literature so far and (1.8) seems to be the first one for the biharmonic
Laplacian. Note that, in contrast to (1.8) and the Laplacian problem involving (1.6), we do not know ground
state solutions to (1.1) explicitly. Hence the exact computation of CN,log remains an open question.
     The paper is organized as follows. In Section 2 we prove Theorem 1.1 and in Section 3 we obtain the
Pohožaev-type result. The main result of Section 4 is a general variant of Lion’s lemma (Lemma 4.1) in
D 2,2 (RN ), which is crucial for the proof of Theroem 1.3 given in Section 5. The last Section 6 is devoted to
the biharmonic logarithmic Sobolev inequality.
4                                         J. MEDERSKI AND J. SIEMIANOWSKI

                             2. Regularity theory and proof of Theorem 1.1
      Let N , k ∈ N and 1 ≤ p < ∞ with N > kp. We define D k,p (RN ) as a completion of the space
C0∞ (RN ) with respect to the norm
                                                                         1
                                                                             p
                                            X
                         kukDk,p :=                kD   α
                                                             ukpLp (RN )        ,    u ∈ C0∞ (RN ).
                                            |α|=k

Hence
                                                               Np
(2.1)                          D k,p(RN ) ⊂ D k−l, N−lp (RN ),                       0 ≤ l ≤ k,
and
                       k
                       X X
(2.2)                                kD α uk        Np           ≤ ckukDk,p ,           u ∈ D k,p (RN ).
                                              L N−jp (RN )
                       j=0 |α|=k−j

    We fix an open set Ω ⊂ RN . We recall that by the standard approach based on mollifiers and the
Calderon–Zygmund Lp –estimates for higher order elliptic operators [22, (2.6)] we have the following
lemma.
   L EMMA 2.1. Let 1 < p < ∞ and k be a positive integer. If w ∈ Lploc (Ω) and ∆k w ∈ Lploc (Ω), then
      2k,p
w ∈ Wloc   (Ω).
                        2,2
                            (Ω) is a weak solution to (1.1), where g satisfies (1.2). Clearly u ∈ L2loc (Ω). Fix
                                                                                                           ∗∗
   Suppose that u ∈ Wloc
U ⊂⊂ Ω. Since N +4 < 4 and N2N
                2N      N                 ∗∗ N −4
                                   +4 = 2 N +4 , by the Hölder inequality
              Z                          Z
                             2N                     2N           N   8      ∗∗ N−4
                  |g(x, u)|  N+4 dx ≤ c      |a(x)| N+4 + |a(x)| 4 N+4 |u|2 N+4 dx < ∞,
                  U                            U
for some constant c > 0. Then, by the distributional equality
                                                                           2N
                                            ∆2 u = g(x, u) ∈ Lloc
                                                               N+4
                                                                   (Ω),
                                          4, 2N
and Lemma 2.1, we infer that u ∈ WlocN+4 (Ω).
    Now the crucial step is the following lemma.
                                          4,p
      L EMMA 2.2. Let p ≥ N2N
                            +4 and u ∈ Wloc (Ω) be a weak solution to (1.1), where g satisfies (1.2). Then
                                (
                                   N p/N −5p
                                 Lloc        (Ω),                if 5p < N,
                            u∈     q
                                 Lloc (Ω) for every 1 ≤ q < ∞, if 5p ≥ N.
                                                                                             4,p
      P ROOF. If 4p ≥ N , then the conclusion follows immediately by the Sobolev embedding Wloc  (Ω) ⊂
Lqloc (Ω), q ≥ 1. Thus, we can clearly assume that 4p < N . Let us define
                                      (
                                          g(x,u(x))
                                            u(x) χ{x∈Ω||u(x)|>1} (x),                for u(x) 6= 0,
                           ã(x) :=
                                        0                                            for u(x) = 0,
                           b(x) := g(x, u(x))χ{x∈Ω||u(x)|≤1} (x),
                                                                    N/4
and observe that g(x, u) = ã(x)u + b(x) and ã, b ∈ Lloc (Ω).
    Let U be an arbitrary open bounded subset of Ω such that U ⊂ U ⊂ Ω. We find an open bounded
V with C ∞ -smooth boundary such that U ⊂ V ⊂ V ⊂ Ω. Indeed, let ξ ∈ C0∞ (Ω) be a smooth cut-off
function such that ξ ≡ 1 on U and 0 ≤ ξ ≤ 1. By Sard’s theorem, there is a regular value c ∈ (0, 1).
Then V = ξ −1 ((c, 1]) is an open bounded subset with the smooth boundary ∂V = ξ −1 ({c}) satisfying
U ⊂ V ⊂ V ⊂ Ω.
                              BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                               5

    Now take η ∈ C0∞ (V ) such that η = 1 on U and 0 ≤ η ≤ 1. We restrict our problem to V . By the
assumption u ∈ W 4,p (V ) is a distributional solution of
(2.3)                                   ∆2 u = ã(x)u + b(x)           in V
and ã, b ∈ LN/4 (V ). We define
                                                    v := uη.
Certainly, we have v ∈ W 4,p (V ) ⊂ H 2 (V ) and v ∈ H01 (V ), since supp η ⊂⊂ V . Standard calculations
yield
                                                  X
             ∆2 v = (∆2 u)η + 4∇∆u · ∇η + 4              ∇uxi · ∇ηxi + 2∆u∆η + 4∇u · ∇∆η + u∆2 η
                                                  i=1N
(2.4)                          |                                       {z                          }
                                                                    =:K(u)

                 =: (∆2 u)η + K(u).
Observe that u ∈ W 4,p (V ) ⊂ W 3,p (V ), p∗ = NN−p
                                                  p
                                                    and η ∈ C0∞ (V ) imply that
                                    ∗



(2.5)                 kK(u)kLp∗ (V ) ≤ ckukW 3,p∗ (V ) kηkW 4,∞ (V ) ≤ c(η)kukW 4,p (V ) ,
for some constant c(η) > 0.
     In view of [25, Lemma B.2], for every ε > 0 there are qε ∈ LN/4 (V ) and fbε ∈ L∞ (V ) such that
(2.6)                                       ã(x)v = qε (x)v + fbε ,
and
(2.7)                                             kqε kLN/4 (V ) ≤ ε.
By (2.4), (2.3) and (2.6) we get
                                        ∆2 v = (∆2 u)η + K(u)
(2.8)                                        = ã(x)v + b(x)η + K(u)
                                             = qε (x)v + fε + K(u),
where
                                                              N
(2.9)                                    fε := fbε + b(x)η ∈ L 4 (V ).
     We recall some needed regularity results from [2] (see also [12, Thm 2.20]), for all 1 < q < ∞,
ḡ ∈ Lq (V ), there exists a unique strong solution u ∈ W 4,q (V ) to the problem
                                            (
                                              (−∆)2 u = ḡ in V,
                                              u = ∆u = 0 on ∂V.
satisfying
                                          kukW 4,q (V ) ≤ cq kḡkLq (V ) ,
where cq > 0 depends only on N , q and V . Denote by Tq the linear operator g 7→ u considered as an
operator from Lq (V ) to W 4,q (V ) and rewrite the above inequality as
(2.10)                                  kTq ḡkW 4,q (V ) ≤ cq kḡkLq (V ) .
Obviously, Tq is the Lq -inverse of the bilaplacian (−∆)2 considered with the Navier boundary conditions
u = ∆u = 0 on ∂V .
   Now we can rephrase (2.8) in the language of operators
(2.11)                                        v − Aε,q v = hε,q ,
where Aε,q v := Tq (qε v) and hε,q := Tq (fε + K(u)).
   We consider two cases separately.
6                                            J. MEDERSKI AND J. SIEMIANOWSKI

                                                      Case I: 5p < N .
                                                                                                             Np
    In what follows we take q = p∗ . By the Sobolev embedding W 4,p (V ) ⊂ L N−5p (V ), (2.10), (2.9) and
                                                                                                ∗


(2.5), we have
                           khε,p∗ k     Np        ≤ cSobolev kTp∗ (fε + K(u))kW 4,p∗ (V )
                                   L N−5p (V )
                                                  ≤ cSobolev cp∗ kfε + K(u)kLp∗ (V )
                                                                                       
(2.12)                                            ≤ c kfε k N          + kK(u)kLp∗ (V )
                                                              L 4 (V )
                                                                                         
                                                  ≤ c kfε k N4         + c(η)kukW 4,p (V ) ,
                                                                    L     (V )

                                                                                                                  Np        Np
where c > 0 is some constant. We estimate the norm of the linear operator Aε,p∗ : L N−5p (V ) → L N−5p (V )
                                                               Np
applying the Sobolev embedding W 4,p (V ) ⊂ L N−5p (V ) and (2.10)
                                             ∗



(2.13)         kAε,p∗ vk     Np         ≤ cSobolev kTp∗ (qε v)kW 4,p∗ (V ) ≤ cSobolev cp∗ kqε vkLp∗ (V ) .
                          L N−5p (V )

We use the Hölder inequality with the exponents
                                                      1             1            1
                                                      N
                                                           +     Np
                                                                          =
                                                      4
                                                                                 p∗
                                                                N −5p

to obtain
(2.14)                             kqε vkLp∗ (V ) ≤ kqε kLN/4 (V ) kvk                     Np        .
                                                                                      L N−5p (V )

In view of (2.13), (2.14) and (2.7) we gain
                                 kAε,p∗ vk       Np            ≤ cSobolev cp∗ εkvk              Np       .
                                             L N−5p (V )                                   L N−5p (V )

We choose ε := (2cSobolev cp∗ )−1 to deduce
                                                                                          1
(2.15)                                        kAε,p∗ k       Np      Np               ≤     .
                                                          L N−5p →L N−5p                  2
                                                          Np
Then (I − Aε,p∗ ) is invertible on the space L N−5p (V ) with the norm bounded by 2 and by (2.11)
(2.16)                                           v = (I − Aε,p∗ )−1 hε,p∗ ,
so by the above and by (2.12)

                    kvk     Np          ≤ (I − Aε,p∗ )−1                   khε,p∗ k Np
                                                                          Np              Np
                        L N−5p (V )                                     L N−5p →L N−5p
                                                                                   L N−5p (V )
                                                                             
                                        ≤ 2c kfε kL∞ (V ) + c(η)kukW 4,p (V ) < ∞.
               Np                                                                                                      Np
                                                                                         N−5p
Hence v ∈ L N−5p (V ) and, since u = v on U ⊂ Ω and U is arbitrary, we finally get u ∈ Lloc   (Ω) as
claimed. This finishes the proof of Case I.

                                                      Case II: 5p ≥ N .

    We proceed similarly as in Case I. Fix any NN−4p
                                                  p
                                                     ≤ q < ∞ and define r := NN+4q
                                                                                q
                                                                                   . Then we have
1 < r < N4 ≤ NN−p
                p
                  . We employ the Sobolev embedding W 4,r (V ) ⊂ Lq (V ), (2.10), (2.9) and (2.5) to
                                    BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                  7

estimate
                                khε,r kLq (V ) ≤ cSobolev kTr (fε + K(u))kW 4,r (V )
                                                ≤ cSobolev cr kfε + K(u)kLr (V )
                                                                                 
(2.17)                                          ≤ c kfε k N          + kK(u)kLp∗
                                                            L 4 (V )
                                                                                       
                                                ≤ c kfε k N4         + c(η)kukW 4,p (V ) ,
                                                              L     (V )

for some constant c > 0. We bound the norm of Aε,r : Lq (V ) → Lq (V ) by exploiting the Sobolev
embedding W 4,r (V ) ⊂ Lq (V ) and (2.10)
(2.18)                   kAε,r kLq (V ) ≤ cSobolev kTr (qε v)kW 4,r (V ) ≤ cSobolev cr kqε vkLr (V ) .
We use Hölder’s inequality with exponents
                                                      1            1           1
                                                     N
                                                          +    Nr
                                                                           =
                                                     4        N −4r
                                                                               r
                                                              | {z }
                                                                  = 1q

and (2.7) to obtain
(2.19)                            kqε vkLr (V ) ≤ kqε k N4             kvkLq (V ) ≤ εkvkLq (V ) .
                                                          L   (V )

We choose ε = (2cSobolev cr )−1 and from (2.18), (2.19) deduce that
                                                               1
                                              kAε,r kLq →Lq ≤ .
                                                               2
As in the last part of Case I, we then show that v ∈ L (V ). This implies that u ∈ Lq (U ) and, since U ⊂ Ω
                                                         q

and q ≥ NN−4pp
                were arbitrary, the proof of Case II is completed.                                        

                                  2,2                                                                    4, 2N
Proof of Theorem 1.1. Let u ∈ Wloc    (Ω) be a weak solution to (1.1). Then u ∈ WlocN+4 (Ω). We show
that u ∈ Lloc (Ω), for every q ≥ 1. If N = 5 or N = 6, then, by Lemma 2.2, u ∈ Lqloc (Ω), for every
           q

q ≥ 1, and we are done. If N > 6, then we define p1 := N2N+4 , 5p1 < N , and we use Lemma 2.2 to obtain
          Np1

                 (Ω). Since NN−5p
                               p1
                                    = N2N
         N−5p1
u ∈ Lloc                          1     −6 ,
                                                   N p1 N − 6      2N   N
                                    p1 < p2 :=                  =      < .
                                                  N − 5p1 N + 2   N +2  4
Fix U ⊂⊂ Ω. Observe that p2 N 8+2 = N4 and by the Hölder inequality
    Z                     Z                Z           N+2
                                                                8 Z      Np1      N−6
                                                                 N+2                 N+2
       |g(x, u)|p2 dx ≤ c   |a(x)|p2 dx + c     |a(x)|p2 8 dx         |u| N−5p1 dx       <∞
     U                          U               U                          U
                                                               p2                    4,p1
                                             2
for some constant c > 0. Therefore we get ∆ u = g(x, u) ∈ Lloc (Ω). Since u ∈ Wloc        (Ω) ⊂ Lploc2 (Ω), we
                             4,p2
use Lemma 2.1 to get u ∈ Wloc (RN ). Let K be the largest natural number less than N 2−4 . We continue
applying Lemma 2.2 in this fashion and get a finite sequence (pk )K
                                                                  k=1 such that for k = 1, ..., K
                                                  2N
                                        pk :=            ,
                                              N + 6 − 2k
                                           N + 6 − 2k   N
                                        pk            = ,
                                               8         4
                                                 N pk N − 4 − 2k
                                        pk+1 =                    ,                   if k ≥ 1.
                                               N − 5pk N + 4 − 2k
8                                      J. MEDERSKI AND J. SIEMIANOWSKI

                                                                      NpK

By the definition of K, we get 5pK < N , NN−5p   pK                  N−5p
                                                   K
                                                      ≥ N and u ∈ Lloc K (Ω). Finally, by Lemma 2.2 we
obtain that u ∈ Lloc (Ω), for every q ≥ 1. Since ∆2 u = g(x, u) ∈ Lqloc (Ω), for every 1 ≤ q < ∞, by
                   q
                     4,q                                              3,α
Lemma 2.1, u ∈ Wloc      (Ω), q ≥ 1, so by the Sobolev embedding u ∈ Cloc (Ω), for every 0 < α < 1.  

                                            3. Pohožaev identity
Proof of Theorem 1.2. One can find ϕ ∈ C ∞ (R) satisfying ϕ|(−∞,1] ≡ 1, ϕ|[2,∞) ≡ 0 and 0 ≤ ϕ ≤ 1. For
                                                       2
every n ≥ 1, we define ϕn ∈ C0∞ (RN ) by ϕn (x) := ϕ |x|n2 .
                                              3,α           4,q
      By Theorem 1.1, we may assume that u ∈ Cloc (RN ) ∩ Wloc  (RN ), 0 < α < 1, 1 ≤ q < ∞, so
                                      0 = ∆2 u − g(x, u)   a.e. in RN .
Thus, for a.e. x ∈ RN and for every n, we obtain
(3.1)                                  0 = (∆2 u − g(x, u))ϕn x · ∇u.
The following identities hold
        g(x, u)ϕn x · ∇u = div (ϕn G(x, u)x) − G(x, u)x · ∇ϕn − N ϕn G(x, u) − ϕn x · ∂x G(x, u)
and
        ∆2 uϕn x · ∇u = div (ϕn (x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − ϕn ∇(x · ∇u) · ∇(∆u).
We transform the rightmost term of the above equation
ϕn ∇(x · ∇u) · ∇(∆u) = −ϕn ∆u∆(x · ∇u) + ϕn div (∆u∇(x · ∇u))
                         = −ϕn ∆u(2∆u + x · ∇∆u) + div (ϕn ∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u)
                         = −2ϕn (∆u)2 − ϕn ∆ux · ∇∆u + div (ϕn ∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u).
Finally, we rewrite the second term of the above line as follows
                                                    
                                             (∆u)2         1           N
                 ϕn ∆ux · ∇∆u = div ϕn              x − (∆u)2 ∇ϕn · x − ϕn (∆u)2 .
                                               2           2           2
Putting the above identities into (3.1) we get
   0 = −div (ϕn G(x, u)x) + G(x, u)x · ∇ϕn + N ϕn G(x, u) + ϕn x · ∂x G(x, u)
                                                                                             
                                                                                       (∆u)2
          + div (ϕn (x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − div ϕn ∆u∇(x · ∇u) −                x
                                                                                         2
             N −4              1
          −        ϕn (∆u)2 − (∆u)2 x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u)
                2              2
or, equivalently,
                                                                   
                                                             (∆u)2
(3.2) div ϕn G(x, u)x + ∆u∇(x · ∇u) − x · ∇u∇∆u −                  x
                                                               2
              = G(x, u)x · ∇ϕn + N ϕn G(x, u) + ϕn x · ∂x G(x, u) − (x · ∇u)(∇ϕn · ∇∆u)
                                         N −4                1
                                       −       ϕn (∆u)2 − (∆u)2 x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u).
                                            2                2
Fix n ≥ 1 and take R > 0 such that supp ϕn ⊂ BR . By the divergence theorem, we obtain
               Z
          0=       G(x, u)x · ∇ϕn + N ϕn G(x, u) + ϕn x · ∂x G(x, u) − (x · ∇u)(∇ϕn · ∇∆u)
                 BR
                      N −4           1
                 −         (∆u)2 ϕn − (∆u)2 x · ∇ϕn + ∆u∇ϕn · ∇(x · ∇u) dx.
                        2            2
                              BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                  9

Note that
  Z                         Z                                                  Z
−     (x·∇u)(∇ϕn ·∇∆u) dx =              ∆u∇ϕn ·∇(x·∇u)+∆u∆ϕn x·∇u dx−                  div (x · ∇u∆u∇ϕn ) dx.
   BR                              BR                                              BR
                                                                               |               {z       }
                                                                                              =0
Summing up, we have
(3.3) Z
  0=     G(u)x · ∇ϕn + N ϕn G(x, u) + ϕn x · ∂x G(x, u) + 2∆u∇ϕn · ∇(x · ∇u) + ∆u∆ϕn x · ∇u
        BR
                   N −4           1
               −        (∆u)2 ϕn − (∆u)2 x · ∇ϕn dx
        Z            2            2
    =        G(u)x · ∇ϕn + N ϕn G(x, u) + ϕn x · ∂x G(x, u) + 2∆u∇ϕn · ∇(x · ∇u) + ∆u∆ϕn x · ∇u
        RN
                 N −4                 1
               −        (∆u)2 ϕn − (∆u)2 x · ∇ϕn dx.
                    2                 2
We return to (3.3) and pass to the limit as n → ∞ to obtain
                         Z                   Z                            Z
                                                                     N −4
                 0=N          G(x, u) dx +       x · ∂x G(x, u) dx −          |∆u|2 dx,
                           RN                 RN                       2   RN
where we used Lebesgue’s dominated convergence theorem and the properties of ϕn . The proof is com-
pleted.                                                                                          

                                                4. Lions lemma
    We prove a biharmonic variant of Lion’s lemma, cf. [15, 16], [20, Section 2].
    L EMMA 4.1. Suppose that (un ) is bounded in D 2,2 (RN ) and for some r > 0
                                               Z
(4.1)                                lim sup            |un |2 dx = 0.
                                     n→∞ y∈RN         B(y,r)

Then                                 Z
                                              Ψ(un ) dx → 0     as n → ∞
                                        RN
for every continuous Ψ : R → R satisfying
                                              Ψ(s)             Ψ(s)
(4.2)                                   lim           = lim            = 0.
                                        s→0 |s|2        |s|→∞ |s|2
                                                 ∗∗               ∗∗



    We prove the following result, which implies the variant of Lions’s lemma in D 2,2 (RN ).
     L EMMA 4.2. Suppose that (un ) ⊂ D 2,2 (RN ) is bounded. Then un (· + yn ) ⇀ 0 in D 2,2 (RN ) for any
(yn ) ⊂ ZN if and only if           Z
                                              Ψ(un ) dx → 0     as n → ∞
                                        RN
for any continuous Ψ : R → R satisfying (4.2).
     P ROOF. Let (un ) be a sequence in D 2,2 (RN ) be such that un (· + yn ) ⇀ 0 in D 2,2 (RN ) for every
(yn ) ⊂ ZN . Take any ε > 0 and 2∗ < p < 2∗∗ and suppose that Ψ satisfies (4.2). Then we find 0 < δ < M
and c(ε) > 0 such that
                                  Ψ(s) ≤ ε|s|2
                                                       ∗∗
                                                            for |s| ≤ δ,
                                                      2∗∗
                                  Ψ(s) ≤ ε|s|     for |s| > M,
                                                p
                                  Ψ(s) ≤ c(ε)|s|   for |s| ∈ (δ, M ].
10                                        J. MEDERSKI AND J. SIEMIANOWSKI

Let us define (wn ) by
                                      (
                                       |un (x)|                                  for |un (x)| > δ,
                            wn (x) :=
                                       |un (x)|2 /2 δ1−2 /2
                                                ∗∗ ∗    ∗∗ ∗
                                                                                 for |un (x)| ≤ δ.
We are about to show that (wn ) is bounded in W 1,2 (RN ). First of all, we have
                                                             ∗

               Z                     Z                              Z
                           2∗                   2∗ −2∗∗      2∗∗
                                                                              |un |2 dx
                                                                                    ∗
                   |wn (x)| dx =              δ         |un | dx +
                  RN                       {|un |≤δ}                                  {|un |≥δ}
                                                       Z                              Z
                                                                                     |un |2
                                                                                                             ∗∗

                                     = δ2 −2                      |un |2 dx +
                                           ∗      ∗∗                    ∗∗
                                                                                        2∗∗ −2∗
                                                                                                dx
                                                 {|un |≤δ}              {|un |>δ} |un |
(4.3)                                           Z                      Z
                                                                                  |un |2
                                                                                         ∗∗

                                     ≤ δ2 −2               |un |2 dx +
                                         ∗   ∗∗                  ∗∗
                                                                                    2∗∗ −2∗
                                                                                             dx
                                                 {|un |≤δ}              {|un |>δ} δ
                                                Z
                                        2∗ −2∗∗
                                                     |un |2 dx.
                                                           ∗∗
                                     =δ
                                                        RN
By the absolute continuous characterization (see §1.1.3 in [18]), we infer that each un is absolutely contin-
uous on almost every line parallel to the 0xi -axis, for i = 1, . . . , N . Thus the same holds for each wn , since
wn = F (un ), where F (t) = min{δ1−2 /2 |t|2 /2 , |t|} is a globally Lipschitz function. Moreover, for
                                              ∗∗   ∗   ∗∗ ∗


every i = 1, . . . , N , we have
                               ( ∗∗
                                 2     1−2∗∗ /2∗ sign(u )|u |2∗∗ /2∗ −1 ∂un , for |u (x)| ≤ δ,
                        ∂wn       2∗ δ                  n   n           ∂xi          n
                             =             ∂un
                        ∂xi      sign(un ) ∂xi ,                              for |un (x)| > δ.
Thus
        Z                       ∗∗ 2∗            Z                                        Z
              ∂wn 2                                                                 2∗
                                                                                                        ∂un 2
                       ∗                                                                                     ∗
                                 2         2∗ −2∗∗                  2∗∗ −2∗ ∂un
                    dx =                 δ                     |un |                   dx +                    dx
           RN ∂xi                2∗                  {|un |≤δ}                 ∂xi           {|un |>δ} ∂xi
                                ∗∗ 2∗ Z                               Z
                                                       ∂un 2                        ∂un 2
                                                              ∗                           ∗
                                 2
(4.4)                      ≤                                     dx +                       dx
                                 2∗        {|un |≤δ} ∂xi                  {|un |>δ} ∂xi
                                ∗∗ 2∗ Z
                                                 ∂un 2
                                                        ∗
                                 2
                           ≤                               dx.
                                 2∗        RN ∂xi
By (4.3), (4.4) (again using an absolute continuous characterization on lines from §1.1.3 [18]) and the fact
that (un ) is bounded in D 2,2 (RN ), we conclude that (wn ) is bounded in W 1,2 (RN ).
                                                                                        ∗


     Let Ω = (0, 1)N and y ∈ RN be arbitrary. Then, by the Sobolev inequality one has
 Z                      Z                                      Z
        Ψ(un ) dx =                            Ψ(un ) dx +                                    Ψ(un ) dx
   Ω+y                    (Ω+y)∩{δ<|un |≤M }                    (Ω+y)∩({|un |>M }∪{|un |≤δ})
                              Z                                      Z
                                                    |wn |p dx + ε                                   |un |2 dx
                                                                                                          ∗∗
                    ≤ c(ε)
                               (Ω+y)∩{δ<|un |≤M }                               (Ω+y)∩({|un |>M }∪{|un |≤δ})
                               Z                                       Z                       1−2∗ /p        Z
                                               2∗                2∗                       p
                                                                                                                            |un |2 dx,
                                                                                                                                 ∗∗
                    ≤ c(ε)C               |wn |        + |∇wn | dx                    |wn | dx               +ε
                                   Ω+y                                          Ω+y                                   Ω+y

where C > 0 is a constant from the Sobolev inequality. Then we sum the inequalities over y ∈ ZN and get
Z                      Z                                  Z                  !1−2∗ /p     Z
                                                                           p
                                   2∗        2∗
                                                                                                |un |2 dx.
                                                                                                      ∗∗
    Ψ(un ) dx ≤ c(ε)C         |wn | + |∇wn | dx         sup    |wn (· + y)| dx          +ε
 RN                          RN                                       y∈ZN       Ω                                          RN

Let us take (yn ) ⊂ ZN such that
                                     Z                                 Z
                               sup        |wn (· + y)|p dx ≤ 2                 |wn (· + yn )|p dx
                              y∈ZN    Ω                                    Ω
                              BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                   11

for any n ≥ 1. By the assumption un (· + yn ) ⇀ 0 in D 2,2 (RN ) and passing to a subsequence we obtain
un (· + yn ) → 0 in Lp (Ω).
     Since |wn (x)| ≤ |un (x)|, we infer that wn (· + yn ) → 0 in Lp (Ω). Therefore
                                     Z                            Z
                                                                       |un |2 dx,
                                                                             ∗∗
                             lim sup       Ψ(un ) dx ≤ ε lim sup
                             n→∞      RN                  n→∞       RN
and since ε > 0 is arbitrary, the assertion follows.
    On the other hand, suppose that un (· + yn ) does not converge to 0 in D 2,2 (RN ), for some (yn ) in ZN ,
and Ψ(un ) → 0 in L1 (RN ). We may assume that un (· + yn ) → u0 6= 0 in Lp (Ω) for some bounded domain
Ω ⊂ RN and 1 < p < 2∗∗ . Take any ε > 0, q > 2∗∗ and let us define Ψ(s) := min{|s|p , εp−q |s|q } for
s ∈ R. Then
              Z                       Z                              Z
                    Ψ(un ) dx ≥                              p
                                                        |un | dx +                     εq−p |un |q dx
                RN                      Ω+yn ∩{|un |≥ε}                Ω+yn ∩{|un |≤ε}
                                      Z                   Z
                                  =          |un |p dx +                     εp−q |un |q − |un |p dx
                                        Ω+yn                 Ω+yn ∩{|un |≤ε}
                                      Z
                                  ≥          |un |p dx − εp |Ω|.
                                      Ω+yn


Thus we get un (· + yn ) → 0 in Lp (Ω) and this contradicts u0 6= 0.                                        
Proof of Lemma 4.1. Suppose that there is (yn ) ⊂ ZN such that un (· + yn ) does not converge weakly to 0
in D 2,2 (RN ). Since un (· + yn ) is bounded, there is u0 6= 0 such that, up to a subsequence,
                                      un (· + yn ) ⇀ u0   in D 2,2 (RN ),
as n → ∞. We find y ∈ RN such that u0 χB(y,r) 6= 0 in L2 (B(y, r)). Observe that, passing to a subse-
quence, we may assume that un (· + yn ) → u0 in L2 (B(y, r)). Then, in view of (4.1)
                         Z                             Z
                                  |un (· + yn )|2 dx =          |un |2 dx → 0
                             B(y,r)                       B(yn +y,r)

as n → ∞, which contradicts the fact un (· + yn ) → u0 6= 0 in L2 (B(y, r)). Therefore un (· + yn ) ⇀ 0 in
D 2,2 (RN ) for any (yn ) ⊂ ZN and by Lemma 4.2 we conclude.                                            

                                           5. Proof of Theorem 1.3
    In this section we adapt a variational approach from [20, Section 3] for the bi-Laplacian. Let
                                          (R
                                               s
                                              0  max{−g(t), 0} dt for s ≥ 0,
                               G− (s) :=    R  0
                                              s max{g(t), 0} dt    for s < 0.
Notice that G+ , G− ≥ 0 and G = G+ − G− .
    First, we sketch our approach with an approximation Jε of J and present some auxiliary lemmas. The
proof of Theorem 1.3 is postponed to the end of the section. Let
                       g+ (s) := G′+ (s) and     g− (s) := g+ (s) − g(s),      s ∈ R.
                       Rs
Notice that G− (s) =   0 g− (t) dt ≥ 0, for s ∈ R. In view of (g1) and (g3), there is some c > 0 such that for
every s ∈ R
                                              |G+ (s)| ≤ c|s|2 ,
                                                               ∗∗
(5.1)
so G+ (u) ∈ L1 (RN ) whenever u ∈ D 2,2 (RN ) ⊂ L2 (RN ). On the other hand, G− (u) may not be
                                                          ∗∗


integrable, for u ∈ D 2,2 (RN ), unless G− (u) ≤ c|u|2 for some c > 0. To overcome this problem, for
                                                      ∗∗
12                                         J. MEDERSKI AND J. SIEMIANOWSKI

ε ∈ (0, 1), we define ϕε : R → [0, 1] by
                                                (
                                                       1
                                                            |s|2 −1
                                                                ∗∗
                                                    ε2∗∗ −1
                                                                               for |s| ≤ ε,
                                    ϕε (s) :=
                                                    1                          for |s| ≥ ε.
We introduce a new functional
                                       Z                    Z                               Z
                                   1
(5.2)                    Jε (u) :=                  2
                                               |∆u| +                Gε− (u) dx −                  G+ (u) dx,
                                   2      RN                    RN                          RN
                    Rs
where Gε− (s) :=    0 ϕε (t)g− (t) dt, s ∈ R. By (g0), there is c(ε) > 0 such that

                                     |ϕε (s)g− (s)| ≤ c(ε)|s|2
                                                                           ∗∗ −1
(5.3)                                                                              ,     s ∈ R.
This implies that Gε− (s) ≤ c(ε)|s| for any s ∈ R and some constant c(ε) > 0 depending on ε > 0. Hence,
                                    2∗∗

for ε ∈ (0, 1), Jε is well-defined on D 2,2 (RN ), continuous and Jε′ (u)(v) exists for any u ∈ D 2,2 (RN ) and
v ∈ C0∞ (RN ). Therefore, we say that u is a critical point of Jε provided that Jε′ (u)(v) = 0 for any
v ∈ C0∞ (RN ).
    We define, for ε ∈ (0, 1),
                Gε := G+ − Gε− ,
                      n                     Z                Z                o
                             2,2   N                 2    ∗∗
                Mε :=  u ∈ D (R ) \ {0} :        |∆u| − 2        Gε (u) dx = 0 ,
                                              RN              RN
                      n                  Z              o
                Pε :=  u ∈ D 2,2 (RN ) :   Gε (u) dx > 0 6= ∅,
                                                        RN
                    cε :=     inf Jε (u).
                             u∈Mε

and introduce the map mPε : Pε → Mε given by
                                                 mPε (u) = u(rε ·),
where
                                   ∗∗ R              1/4        R            1
                                     2 RN Gε (u) dx            2∗∗ RN Gε (u) dx 4
                   rε = rε (u) :=       R                  =                      .
                                                   2                kuk1/2
                                          RN |∆u|
We check that mPε is well-defined. If u ∈ Pε , then
               Z                                    Z
                                     2        4−N
                    |∆(mPε (u)(x)| dx = rε            |∆u|2 dx
                    RN                                              RN
                                                               Z                        4−N
                                                                                            4         N−4
                                                        ∗∗
                                                =       2                Gε (u) dx              kuk 2 kuk2
                                                                    RN
                                                               Z                                          N
                                                        ∗∗                                            kuk 2
                                                =       2                Gε (u) dx             R            N
                                                                    RN                      2∗∗ RN Gε (u) dx 4
                                                               Z                       
                                                        ∗∗
                                                =       2                Gε (u) dx rε−N
                                                                    RN
                                                            Z
                                                = 2∗∗                Gε (mPε (u)(x)) dx.
                                                                RN
                                                                                                                 
     L EMMA 5.1. For every δ > 0 there is cδ > 0 such that
                                    Gε (u + v) − Gε (u) − δ|u|2                        ≤ cδ |v|2
                                                                              ∗∗                 ∗∗



for all u, v ∈ R.
                                   BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                             13

    P ROOF. First, we show that for every δ > 0 there is c(δ) > 0 such that
                           |Gε− (u + v) − Gε− (u)| ≤ δ|u|2            + c(δ)|v|2 ,
                                                                 ∗∗                   ∗∗
(5.4)                                                                                          u, v ∈ R.
Fix δ > 0 and u, v ∈ R. By the mean value theorem, there is θ ∈ (0, 1) such that
                            |Gε− (u + v) − Gε− (u)| ≤ |ϕε (u + θv)g− (u + θv)||v|
                                                        ≤ c(ε)|u + θv|2
                                                                                ∗∗ −1
                                                                                        |v|
                                                                       2∗∗ −1
                                                                                |v| + c1 (ε)|v|2 ,
                                                                                                           ∗∗
                                                        ≤ c1 (ε)|u|
where we used (5.3). We exploit the Young inequality with δ/c1 (ε)
                                    δ                                                             2∗∗
               |u|2
                  ∗∗ −1
                                         |u|(2 −1)p + c2 (δ, ε)|v|q ,                                   , q = 2∗∗ ,
                                              ∗∗
                          |v| ≤                                              where p =
                                  c1 (ε)                                                        2∗∗ − 1
to obtain
                                  |Gε− (u + v) − Gε− (u)| ≤ δ|u|2            + c3 (δ, ε)|v|2 ,
                                                                        ∗∗                       ∗∗



what proves the assertion.
   Now, we show that for every δ > 0 there is c(δ) > 0 such that
                          G+ (u + v) − G+ (u) − δ|u|2            ≤ c(δ)|v|2 ,
                                                            ∗∗                   ∗∗
                                                                                               u, v ∈ R.
Fix δ > 0 and u, v ∈ R. By (g1) and (g3), there are 0 < η < M such that
                                                             2       2∗∗
                                                 G+ (s) ≤     ∗∗ δ|s|    ,
                                                            22
if |s| < η or |s| > M . We consider four cases.
Case I: |u + v| < η or |u + v| > M .
We use the fact that G+ ≥ 0 and obtain
                                                                 2                                          
                                                                       δ|u + v|2           ≤ δ |u|2 + |v|2
                                                                                      ∗∗           ∗∗     ∗∗
              G+ (u + v) − G+ (u) ≤ G+ (u + v) ≤                 2∗∗
                                                                                                               ,
                                                      2
what proves the assertion.
Case II: η ≤ |u + v| ≤ M and |v| > M .
There is c > 0 such that G+ (s) ≤ c|s|2 , for every s ∈ R, so
                                       ∗∗



                      G+ (u + v) − G+ (u) ≤ G+ (u + v) ≤ c|u + v|2                         ≤ cM 2          ≤ c|v|2
                                                                                  ∗∗                  ∗∗         ∗∗



and we are done.
Case III: η ≤ |u + v| ≤ M and η/2 ≤ |v| ≤ M .
The set C := (u, v) ∈ R2 | η ≤ |u + v| ≤ M and η/2 ≤ |v| ≤ M                                  is compact and the function h :
                                                            ∗∗
                                     G+ (u+v)−G+ (u)−δ|u|2
C → R, given by h(u, v) :=                    |v|2∗∗
                                                         , is continuous. Thus, there is c(δ) > 0 such that
max(u,v)∈C h(u, v) ≤ c(δ) and we are done.
Case IV: η ≤ |u + v| ≤ M and |v| < η/2.
By the continuity of g+ and by (g0), there is c(η) such that
                                                                        η
                                  |g+ (s)| ≤ c(η)|s|2 −1 ,
                                                      ∗∗
                                                                   |s| ≥ .
                                                                        2
By the mean value theorem, there is θ ∈ (0, 1) such that
                                        G+ (u + v) − G+ (u) = g+ (u + θv)v.
Notice that |u + θv| ≥ |u + v| − (1 − θ)|v| > η − η/2 = η/2, so combining the above we obtain
                                   G+ (u + v) − G+ (u) ≤ c(η)|u + θv|2
                                                                                       ∗∗ −1
                                                                                               |v|.
We then proceed as in the first part of the proof.
14                                          J. MEDERSKI AND J. SIEMIANOWSKI

     Finally, we use the above results to deduce
                                                                                   
                  Gε (u + v) − Gε (u) = G+ (u + v) − G+ (u) − Gε− (u + v) − Gε− (u)
                                            ≤ δ|u|2 + c(δ)|v|2 + |Gε− (u + v) − Gε− (u)|
                                                    ∗∗              ∗∗

                                                                  
                                            ≤ 2 δ|u|2 + c(δ)|v|2
                                                     ∗∗         ∗∗
                                                                     .
                                                                                                          
     L EMMA 5.2. Suppose that (un ) ⊂ Mε , Jε (un ) → cε and
                            e 6= 0 in D 2,2 (RN ), un (x) → u
                       un ⇀ u                               e(x)             for a.e. x ∈ RN
         e ∈ D 2,2 (RN ). Then un → u
for some u                          e, u
                                       e is a critical point of Jε and Jε (e
                                                                           u) = cε .
     P ROOF. It follows, by Lemma 5.1, that for every δ > 0 theres is c(δ) > 0 such that
                         |Gε (u + v) − Gε (u)| ≤ δ|u|2            + c(δ)|v|2 ,
                                                             ∗∗             ∗∗
                                                                                      u, v ∈ R.
Thus taking any v ∈ C0∞ (RN ) and t ∈ R we observe that (Gε (un + tv) − Gε (un )) is uniformly integrable
and tight. In view of Vitali’s convergence theorem we have
                         Z                                  Z
                    lim        Gε (un + tv) − Gε (un ) dx =       u + tv) − Gε (e
                                                              Gε (e             u) dx.
                   n→∞ RN                                            RN
Since each un ∈ Mε , we get
                                Z                        Z           ∗∗   Z
                            1                 2                      2
            cε ← Jε (un ) =            |∆un | dx −    Gε (un ) dx =      −1     Gε (un ) dx,
                            2       RN             RN                 2      RN
so
                                        Z                                       −1
                                                           1             1   1
(5.5)                     A := lim           Gε (un ) dx = ∗∗              −           cε > 0.
                                n→∞      R N              2              2 2∗∗
Combining the above we have
              Z                          Z               Z                     Z
          lim      Gε (un + tv) dx = lim   Gε (un ) dx +          u + tv) dx −
                                                              Gε (e                 Gε (e
                                                                                        u) dx
         n→∞ RN                     n→∞ RN                RN                     RN
(5.6)                                    Z                  Z
                                   =A+         u + tv) dx −
                                           Gε (e                 Gε (e
                                                                     u) dx.
                                                    RN                           RN
By (5.5) and Lemma 5.1, un + tv ∈ Pε for sufficiently large n and sufficiently small |t|. Thus and by (5.6),
for sufficiently small |t|, we have
                                 Z                     N−4 Z                     N−4 !
                             1                            N                           N
                        lim            Gε (un + tv) dx        −        Gε (un ) dx
                      n→∞ t         RN                              RN
                                  Z                     Z               N−4           !
                        1                                                  N        N−4
                    =          A+          u + tv) dx −
                                       Gε (e                  Gε (e
                                                                  u) dx       −A N        .
                         t          RN                     RN

and, consequently, by the Lebesgue dominated convergence theorem
(5.7)                                                              !
                 Z                     Z               N−4                    Z
        1                                                 N    N−4     N − 4 −4
    lim      A+            u + tv) dx −
                       Gε (e                 Gε (e
                                                 u) dx       −A N    =      AN      gε (e
                                                                                        u)v dx,
    t→0 t           RN                    RN                            N        RN

where gε := G′ε = g+ − ϕε g− .
   If un + tv ∈ Pε , then Jε (mPε (un + tv)) ≥ cε , so
                                                   Z
                                          1     1
                        rε (un + tv)4−N
                                            −             |∆(un + tv)|2 dx ≥ cε .
                                          2 2∗∗        RN
                              BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                               15

Raising both sides to the 4/N -power yields
                         4 Z                           Z                     N−4
                 1     1 N                    2
                                                      4
                                                         ∗∗
                                                                                  N
(5.8)              − ∗∗           |∆(un + tv)| dx ≥ cε 2
                                                     N
                                                               Gε (un + tv) dx       .
                 2 2           RN                           RN
Assumptions un ∈ Mε and Jε (un ) → cε imply that
                                   Z                            
                                              2           1    1 −1
(5.9)                                   |∆un | dx → cε      −         .
                                    RN                    2 2∗∗
For all n and t, we have
           Z                    Z                   Z                        Z             
                              t          2       1                    2                 2
                ∆un ∆v dx +          |∆v| dx =            |∆(un + tv)| dx −       |∆un | dx .
             RN               2 RN               2t    RN                      RN
Hence, by (5.8) and since un ∈ Mε , for t > 0,
 Z                     Z
                     t
      ∆un ∆v dx +         |∆v|2 dx ≥
   RN                2 RN
                    −4  Z                        N−4  Z                     N−4 Z              4!
 1      4   1     1    N
                           ∗∗
                                                      N
                                                              ∗∗
                                                                                   N
                                                                                                  2
                                                                                                       N
       N
      cε      − ∗∗        2        Gε (un + tv) dx       − 2        Gε (un ) dx             |∆un | dx     .
2t          2 2                 RN                               RN                      RN

Letting n → ∞, by (5.6), (5.5) and (5.9), we deduce that, for sufficiently small t > 0,
 Z                  Z
                  t
      ∆eu∆v dx +         |∆v|2 dx
   RN             2 RN
                         −4              Z                       Z               N−4            !
         1 N4 1       1    N
                                   ∗∗
                                                                                        N
                                                                                               ∗∗ N−4
      ≥ cε        −               2     A+           u + tv) dx −
                                                 Gε (e                    Gε (e
                                                                              u) dx        − (2 A) N
         2t     2 2∗∗                         RN                       RN
                          Z                     Z                N−4            !
         2∗∗ 4 1                                                     N       N−4
      =     AN        A+            u + tv) dx −
                                Gε (e                 Gε (eu) dx         −A N       .
          2     t           RN                    RN

We pass to the limit as t → 0+ and use (5.7) to get
                      Z                             Z                 Z
                                        2∗∗ N − 4
                           ∆eu∆v dx ≥                    gε (e
                                                             u)v dx =      gε (e
                                                                               u)v dx.
                        RN               2 N          RN                RN
Since v ∈ C0∞ (RN ) was arbitrary we infer that u
                                                e is a critical point of Jε . We use the Pohožaev identity
Theorem 1.2 to the equation ∆2 u = gε (u) with Gε ∈ L1 (RN ), to deduce that u e ∈ Mε , what leads to
                          Z                                   Z
                  1     1                              1      1
  cε ≤ Jε (e
           u) =     − ∗∗            u|2 dx ≤ lim inf
                                  |∆e                     − ∗∗           |∆un |2 dx = lim Jε (un ) = cε ,
                  2 2         R N              n→∞     2     2       R N              n→∞

                                                     u) = cε and kun k → ke
where the weak l.s.c of the norm was used. Thus, Jε (e                                e in D 2,2 (RN ).
                                                                          uk, so un → u
                                                                                                    
   P ROOF OF T HEOREM 1.3. Take a minimizing sequence (un ) in Mε of Jε , i.e., Jε (un ) → cε . Since
un ∈ Mε , n ≥ 1, we have
                                             Z
                                       1   1
                          Jε (un ) =     − ∗∗        |∆un |2 dx → cε ,
                                       2 2       R N

and so (un ) is bounded in D 2,2 (RN ). Moreover, we have
                             Z                   Z                           
                          ∗∗                               2          1    1
                         2         G+ (un ) dx ≥     |∆un | dx →        −       cε .
                              RN                  RN                  2 2∗∗
By the assumption G+ satisfies (4.2), so (4.1) is not satisfied. Passing to a subsequence, we may choose
(yn ) in RN and 0 6= uε ∈ D 2,2 (RN ) such that
               un (· + yn ) ⇀ uε   in D 2,2 (RN ),   un (x + yn ) → uε (x)   for a.e. x ∈ RN ,
16                                          J. MEDERSKI AND J. SIEMIANOWSKI

as n → ∞. In view of Lemma 5.2, uε ∈ Mε is a critical point of Jε at the level cε .
    Choose εn → 0+ . Fix an arbitrary u ∈ M. Since Gε (s) ≥ G(s), for all s ∈ R and ε ∈ (0, 1), we
deduce that            Z                  Z                  Z
                                                           1
                             Gεn (u) dx ≥       G(u) dx = ∗∗      |∆u|2 dx > 0,
                         R N                R N           2   R N

so mPεn (u) ∈ Mεn is well-defined. We have
                                                    ∗∗ R                4−N   Z
                                           1     1      2 RN Gεn (u) dx       4
          Jεn (uεn ) ≤ Jεn (mPεn (u)) =       − ∗∗       R
                                                                  2 dx
                                                                                        |∆u|2 dx
                                           2 2            RN |∆u|                   R N
                                                      |         {z              }
                                                                                   rεn (u)4−N
                                       Z                    N             Z                     − N−4
                              1   1                        2
                                                                 4
                                                                         ∗∗
                                                                                                            4
                      =         − ∗∗                 |∆u| dx             2              Gεn (u) dx
                              2 2               RN                                 RN
                                       Z                    N             Z                 − N−4
                              1   1                        2
                                                                 4
                                                                         ∗∗
                                                                                                        4
                      ≤         − ∗∗                 |∆u| dx             2            G(u) dx
                              2 2               RN                                 RN
                                                                     |                 {z                   }
                                                                               R                − N−4
                                                                             =( RN |∆u|2 dx)       4
                                      Z
                              1   1
                      =         − ∗∗             |∆u|2 dx = J(u).
                              2 2        RN
Thus Jεn (uεn ) ≤ inf M J and
                         Z                        
                                     2       1   1 −1
(5.10)                        |∆uεn | dx ≤     −      inf J,                               for every n.
                           RN                2 2∗∗     M

We have Gε (s) ≤ G1/2 (s), for all s ∈ R and ε ∈ (0, 1/2), so
            Z                     Z                      Z
                                                      1
                  G1/2 (uε ) dx ≥       Gε (uε ) dx = ∗∗      |∆uε |2 dx > 0 =⇒ uε ∈ P1/2 ,
              R N                   R N              2    R N

and some calculations yield
                                   Jε (uε ) ≥ J1/2 (mP1/2 (uε )) ≥ J1/2 (u1/2 ).
Therefore, we get
      Z                  Z                                                           
   ∗∗                                       2    1     1 −1                   1     1 −1
 2        G+ (uεn ) dx ≥        |∆uεn | dx =       −          Jεn (uεn ) ≥       −          J1/2 (u1/2 ) > 0.
       RN                   RN                   2 2∗∗                        2 2∗∗
                                                R
By (5.10), (uεn ) is bounded in D 2,2 (RN ) and RN G+ (uεn ) dx > c > 0, for some constant c. In view of
Lemma 4.1, (4.1) is not satisfied. Passing to a subsequence, there is (yn ) in RN such that uεn (· + yn ) ⇀
u0 6= 0 and uεn (x + yn ) → u0 (x) a.e. in RN . We write u
                                                         en := uεn (· + yn ) for short. Since g− is continuous
and g− (0) = 0, one may check that, for every v ∈ C0∞ (RN ),
                  1
                        un |2 −1 χ{|eun |≤εn} g− (e                                                             a.e. in RN
                             ∗∗
                2∗∗ −1 |e                         un )v        ≤ χ{|eun |≤εn } g− (e
                                                                                   un )v → 0
               εn
and
                                                   un )v − g− (u0 )v → 0 a.e. in RN .
                                 χ{|eun |>εn } g− (e
                                                          
                                                 un |2 −1 |v|, the family {g− (e
                                                      ∗∗
Due to the estimate |g− (e  un )v| ≤ c 1 + |e                                    un )v} is uniformly integrable (and
tight because of the compact support). In view of Vitali’s convergence theorem
   Z
         |ϕεn (e       un )v − g− (u0 )v| dx
               un )g− (e
     RN
          Z                                                       Z
                   1         2∗∗ −1
       ≤         2∗∗ −1 |e
                         un |       χ{|eun |≤εn} g− (e
                                                     un )v dx +                          un )v − g− (u0 )v dx → 0,
                                                                       χ{|eun |>εn } g− (e
            RN εn                                                   RN
                               BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                          17

as n → ∞. Similarly, we obtain
                                     Z                          Z
                                                  un )v dx →
                                              g+ (e                      g+ (u0 )v dx.
                                         RN                      RN
Gathering the above we deduce that
                             Z                Z                   Z
               ′
              Jεn (e
                   un )(v) =       un ∆v dx −
                                  ∆e               g+ (e
                                                       un )v dx +      ϕεn (e
                                                                            un )g− (e
                                                                                    un )v dx
                                N                N                   N
                             ZR               ZR                  ZR
                           →      ∆u0 ∆v dx −      g+ (u0 )v dx +      g− (u0 )v dx.
                                RN                     RN                          RN
     en is a critical point of Jεn , since so is uεn (translation invariance), hence
Each u
                                        Z                   Z
                                            ∆u0 ∆v dx =          g(u0 )v dx,
                                          RN                        RN
i.e., u0 is a weak solution to (1.1). By Lebesgue’s dominated convergence theorem one may show that
                                         Gε−n (e
                                               un ) → G− (u0 )           a.e. in RN ,
as n → ∞, and, on the other hand,
          Z                      Z                          Z                                           
       ∗∗      εn             ∗∗                                             2
      2     G− (e un ) dx = 2                  un ) dx −
                                           G+ (e                     |∆e
                                                                       un | dx ≤ c sup ke
                                                                                        un kD2,2 (RN )       < ∞,
           RN                        RN                         RN                           n≥1

                            en ∈ Mεn , (5.1) and (5.10). By Fatou’s lemma and by the above
where we used the fact that u
                             Z                         Z
                                 G− (u0 ) dx ≤ lim inf     Gε−n (e
                                                                 un ) dx < ∞,
                               RN                     n→∞        RN

namely, we have shown that G− (u0 ) ∈ L1 (RN ). By the Pohožaev identity, we infer that u0 ∈ M. Lastly,
we show that J(u0 ) = inf M J. We use the weak l.s.c. of the norm and (5.10) to find that
                                 Z                                    Z
                          1    1               2                 1    1
              J(u0 ) =      −            |∆u0 | dx ≤ lim inf       −             |∆eun |2 dx
                          2 2∗∗      RN                 n→∞      2 2∗∗      RN
                                        Z
                                 1     1
                     = lim inf     −             |∆uεn |2 dx ≤ inf J.
                         n→∞     2 2∗∗      R N                 M

                                                                                                                    

                                6. Biharmonic logarithmic inequality
                                       R
    L EMMA 6.1. If u ∈ D 2,2 (RN ) and RN |u|2 dx = 1, then
                                 Z               Z             1/2
                                          2                 2
                                      |∇u| dx <         |∆u| dx      .
                                     RN                         RN

                                                                            b of u (whenever possible) as
     P ROOF. We rely on ideas from [4]. Let us define the Fourier transform u
                                               Z
                                         1
                             b(ξ) =
                             u            N/2
                                                     e−ix·ξ u(x) dx, ξ ∈ RN .
                                     (2π)        R N

                      R
If u ∈ D 2,2 (RN ) and RN |u|2 dx = 1, then u ∈ H 2 (RN ) and by the Plancharel theorem
                                 kukL2 (RN ) = kb
                                                ukL2 (RN ) ,
                               k∇ukL2 (RN ) = k c
                                               ∇ukL2 (RN ) = kξb
                                                               ukL2 (RN ) ,
                               k∆ukL2 (RN ) = k c
                                               ∆ukL2 (RN ) = k|ξ|2 u
                                                                   bkL2 (RN ) .
18                                         J. MEDERSKI AND J. SIEMIANOWSKI

By the Cauchy–Schwartz inequality we get
              Z                1/2 Z                                     1/4 Z                       1/4
                           2                                  2        2                            2
                    |ξb
                      u(ξ)| dξ       ≤                    ||ξ| u
                                                               b(ξ)| dξ                       |b
                                                                                               u(ξ)| dξ          .
                       RN                            RN                                  RN
and the assertion follows with the non-strict inequality. Recall that the equality in the Cauchy–Schwartz
inequality holds if and only if |ξ|2 u
                                     b(ξ) = λb
                                             u(ξ) for some λ, what implies ub = 0. Hence the inequality in
the statement is in fact strict.                                                                        
Proof of Theorem 1.4. Observe that the following inequality holds
              Z              N              Z
                               N−4
(6.1)                    2
                    |∆u| dx         ≥ CN,log       |u|2 log |u| dx,                    for any u ∈ D 2,2 (RN ),
                      RN                              RN
where
                                                     11 − N−4
                                                              4
                                                                            4
                                      CN,log = 2∗∗     ∗∗
                                                          −      (inf J) N−4 .
                                                2 2                M
                                                           R
Indeed, it is enough to consider u ∈ D (R ) such that RN |u|2 log |u| dx > 0. We then obtain u(r·) ∈
                                         2,2  N

M, where
                                            ∗∗ R                   1/4
                                             2 RN |u|2 log |u| dx
                                    r :=          R                       .
                                                           2
                                                    RN |∆u|
Hence J(u(r·)) ≥ inf M J and we get (6.1).
    Now note that (6.1) is equivalent to
         Z               N                   n         Z                        o
                           N−4
                |∆u|2 dx       ≥ CN,log max e−α2             |eα u|2 log |eα u| dx , for u ∈ D 2,2 (RN ).
                                                      ∗∗
(6.2)
            RN                                α∈R                 RN
                  R
Assuming
R            that RN |u|2 dx = 1, the maximum of the right hand side of (6.2) is attained at α = N 8−4 −
        2
  RN |u| log |u| dx. Hence we get
                    N        Z                                                      N − 4
                         log         |∆u|2 dx ≥ log(CN,log ) − α2∗∗ + 2α + log
                 N −4            RN                                                        8
that is
             N         Z                             N − 4 −1           8
                                                                                 Z
                                    2
                   log        |∆u| dx ≥ log CN,log             e     +                 |u|2 log |u| dx
          N −4             RN                             8             N − 4 RN
and
                     Z                 N −4                                 Z
             N                                               N − 4 −1 
                log               2
                            |∆u| dx ≥              log CN,log       e       +        |u|2 log |u| dx
              8         R N                   8                  8              R N

thus (1.7) holds.
     We show that the constant in (1.7) is optimal, i.e., there is u ∈ D 2,2 (RN ) such that the equality holds.
First of all, notice that if u0 is a minimizer given by Theorem 1.3, then for u0 we have the equality in (6.1):
                              Z                 N            Z
                                                  N−4
(6.3)                                       2
                                      |∆u0 | dx       = CN,log      |u0 |2 log |u0 | dx.
                                 RN                                        RN
                                             α
We use (6.1) for the family of functions kue0 k 2 u0 ∈ D 2,2 (RN ), α ∈ R, to get
                                               L
         Z                     N                                          Z
                           2
                                N−4
                                                    2∗∗ −2 (2−2∗∗ )α                                eα
(6.4)             |∆u0 | dx           ≥ CN,log ku0 kL 2   e                          |u0 |2 log           u0 dx,       α ∈ R.
             RN                                                                 RN                ku0 kL2
Now let us consider the function f : R → R given by
                                            Z                                                 Z                      N
                                                                     eα                                      2
                                                                                                                      N−4
                           2∗∗ −2 (2−2∗∗ )α
      f (α) := CN,log ku0 kL2 e               |u0 |2 log                   u0 dx −                      |∆u0 | dx
                                                 RN                ku0 kL2                         RN
                                     BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                               19

Note that
                                                              Z
                            ′              N −4                          u0 2        u0
                          f (α) = 0 ⇐⇒ α =      −                              log         dx.
                                             8                    RN   ku0 kL2     ku0 kL2
On the other hand, f attains maximum at α = log(ku0 kL2 ) in view of (6.4) and (6.3), thus
                        Z
                                u0 2         u0            N −4
                                      log          dx =           − log(ku0 kL2 )
                          RN ku0 kL2      ku0 kL2             8
or, equivalently,
                                                        Z
                                               1                              N
                                                             |∆u0 |2 dx =       ,
                                             ku0 k2L2   RN                    4
where we used the fact that u0 ∈ M. Therefore we obtain the equality in (1.7) for the function kuu0 k0 2 .
                                                                                                      L
   Let us now suppose that
                                         (N −4)/N Z           ! Z
               N                 8e
                  log                                   |∆u|2 dx =          |u|2 log |u| dx
                8          CN,log (N − 4)            RN                 RN

for some u ∈ D 2,2 (RN ) such that kukL2 (RN ) = 1. Then
                      Z               N                     Z
                                       N−4
                             |∆u|2 dx         = CN,log e−α2                   |eα u|2 log |eα u| dx
                                                           ∗∗

                                RN                                       RN
                    R
for α = N 8−4 −               2                                                      α
                        RN |u| log |u| dx and the equality in (6.1) holds for u1 := e u. Hence J(u0 ) = inf M J
for
                                                            ∗∗ R                    1/4
                                                            2 RN |u1 |2 log |u1 | dx
                          u0 := u1 (r·) ∈ M,     where r =       R                        .
                                                                            2
                                                                   RN |∆u1 | dx
Let us sketch the proof that u0 is a critical point of J. Firstly, note that, for every v ∈ C0∞ (RN ), G(u0 +v) ∈
L1 (RN ), for G(s) := s2 log |s|. Fix an arbitrary v ∈ C0∞ (RN ). We use the fact that G is C 1 -smooth and
the Lebesgue dominated convergence theorem to get
                            Z                          Z                 Z
                          1
                     lim            G(u0 + tv) dx −          G(u0 ) dx =            g(u0 )v dx.
                     t→0 t      RN                        RN                     RN
                   R
By the continuity, RN G(u0 + tv) dx > 0, for sufficiently small |t| > 0, so (u0 + tv)(r·) ∈ M, where
                                             ∗∗ R                       1/4
                                              2 RN G(u0 + tv) dx
                                      r= R                         2
                                                                               .
                                                RN |∆(u0 + tv)| dx
Hence
                                          J((u0 + tv)(r·)) ≥ inf J = J(u0 )
                                                                   M
or, equivalently,
                      Z                                Z                   (N −4)/N
            1     1 4/N                 2           4/N   ∗∗
              −             |∆(u0 + tv)| dx ≥ J(u0 )     2      G(u0 + tv) dx           .
            2 2∗∗        RN                                  RN

We then proceed similarly as in the last part of the proof of Lemma 5.2 to conclude that
                                    Z                    Z
                                          ∆u0 ∆v dx ≥         g(u0 )v dx,
                                           RN                      RN

which yields that u0 is a critical point of J.
20                                            J. MEDERSKI AND J. SIEMIANOWSKI

    Finally,
     R        we show the estimate of the constant CN,log from Theorem 1.7. Observe that if u ∈ D 2,2 (RN )
and RN |u| dx = 1, then u ∈ H 2 (RN ). In view of Lemma 6.1 and the logarithmic Sobolev inequality
             2

(1.8) we obtain
    Z                                      Z              1/2 !                  Z              
            2               N          2              2             N         2 2             2
         |u| log(|u|) dx <     log               |∆u| dx          =   log                  |∆u| dx ,
      RN                     4       πeN      RN                    8        πeN      RN

and so
                                                            (N −4)/N          2 2
                                                  8e
                                                                           <          .
                                            CN,log (N − 4)                      πeN
                                                                                                                                

                                                    Acknowledgements
    The authors were supported by the National Science Centre, Poland (Grant No. 2017/26/E/ST1/00817).
J. Mederski was also partially supported by the Deutsche Forschungsgemeinschaft (DFG, German Research
Foundation) – Project-ID 258734477 – SFB 1173 during the stay at Karlsruhe Institute of Technology.

                                                          References
 [1] R. A. Adams, Sobolev spaces, Academic Press [A subsidiary of Harcourt Brace Jovanovich, Publishers], New York-London,
     1975. Pure and Applied Mathematics, Vol. 65.
 [2] S. Agmon, A. Douglis, and L. Nirenberg, Estimates near the boundary for solutions of elliptic partial differential equations
     satisfying general boundary conditions. I, Comm. Pure Appl. Math. 12 (1959), 623–727.
 [3] S. S. Antman, Nonlinear problems of elasticity, 2nd ed., Applied Mathematical Sciences, vol. 107, Springer, New York, 2005.
 [4] J. Bellazzini, R. L. Frank, and N. Visciglia, Maximizers for Gagliardo-Nirenberg inequalities and related non-local problems,
     Math. Ann. 360 (2014), no. 3-4, 653–673.
 [5] H. Berestycki and P.-L. Lions, Nonlinear scalar field equations. I. Existence of a ground state, Arch. Rational Mech. Anal. 82
     (1983), no. 4, 313–345.
 [6] H. Brézis and T. Kato, Remarks on the Schrödinger operator with singular complex potentials, J. Math. Pures Appl. (9) 58
     (1979), no. 2, 137–151.
 [7] H. Brezis and E. H. Lieb, Minimum action solutions of some vector field equations, Comm. Math. Phys. 96 (1984), no. 1,
     97–113.
 [8] E. A. Carlen, Superadditivity of Fisher’s information and logarithmic Sobolev inequalities, J. Funct. Anal. 101 (1991), no. 1,
     194–211. MR1132315
 [9] M. del Pino and J. Dolbeault, Best constants for Gagliardo-Nirenberg inequalities and applications to nonlinear diffusions, J.
     Math. Pures Appl. (9) 81 (2002), no. 9, 847–875.
[10] M. del Pino and J. Dolbeault, The optimal Euclidean Lp -Sobolev logarithmic inequality, J. Funct. Anal. 197 (2003), no. 1,
     151–161.
[11] G. Fibich, B. Ilan, and G. Papanicolaou, Self-focusing with fourth-order dispersion, SIAM J. Appl. Math. 62 (2002), no. 4,
     1437–1462.
[12] F. Gazzola, H.-C. Grunau, and G. Sweers, Polyharmonic boundary value problems, Lecture Notes in Mathematics, vol. 1991,
     Springer-Verlag, Berlin, 2010. Positivity preserving and nonlinear higher order elliptic equations in bounded domains.
[13] L. Gross, Logarithmic Sobolev inequalities, Amer. J. Math. 97 (1975), no. 4, 1061–1083.
[14] E. H. Lieb and M. Loss, Analysis, 2nd ed., Graduate Studies in Mathematics, vol. 14, American Mathematical Society, Provi-
     dence, RI, 2001.
[15] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. II, Ann. Inst.
     H. Poincaré Anal. Non Linéaire 1 (1984), no. 4, 223–283.
[16] P.-L. Lions, The concentration-compactness principle in the calculus of variations. The locally compact case. I, Ann. Inst. H.
     Poincaré Anal. Non Linéaire 1 (1984), no. 2, 109–145.
[17] S. Mayboroda and V. Maz’ya, Regularity of solutions to the polyharmonic equation in general domains, Invent. Math. 196
     (2014), no. 1, 1–68.
[18] V. G. Maz’ja, Sobolev spaces, Springer Series in Soviet Mathematics, Springer-Verlag, Berlin, 1985. Translated from the
     Russian by T. O. Shaposhnikova.
[19] J. Mederski, Nonradial solutions of nonlinear scalar field equations, Nonlinearity 33 (2020), no. 12, 6349–6380.
[20] J. Mederski, General class of optimal Sobolev inequalities and nonlinear scalar field equations, J. Differential Equations 281
     (2021), 411–441.
                                    BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS                                               21

[21] V. V. Meleshko, Selected topics in the history of the two-dimensional biharmonic problem, Appl. Mech. Rev. 56 (2003), 33-85.
[22] L. Nirenberg, Estimates and existence of solutions of elliptic equations, Comm. Pure Appl. Math. 9 (1956), 509–529.
[23] P. Pucci and J. Serrin, A general variational identity, Indiana Univ. Math. J. 35 (1986), no. 3, 681–703.
[24] A. P. S. Selvadurai, Partial differential equations in mechanics. 2, Springer-Verlag, Berlin, 2000. The biharmonic equation,
     Poisson’s equation.
[25] R. C. A. M. Van der Vorst, Best constant for the embedding of the space H 2 ∩ H01 (Ω) into L2N/(N−4) (Ω), Differential
     Integral Equations 6 (1993), no. 2, 259–276.
[26] F. B. Weissler, Logarithmic Sobolev inequalities for the heat-diffusion semigroup, Trans. Am. Math. Soc. 237 (1978), 255–
     269.

    (J. Mederski)
    I NSTITUTE OF M ATHEMATICS ,
    P OLISH ACADEMY OF S CIENCES ,
    UL . Ś NIADECKICH 8, 00-656 WARSAW, P OLAND
    AND
    D EPARTMENT OF M ATHEMATICS ,
    K ARLSRUHE I NSTITUTE OF T ECHNOLOGY (KIT),
    D-76128 K ARLSRUHE , G ERMANY
    Email address: jmederski@impan.pl

    (J. Siemianowski)
    FACULTY OF M ATHEMATICS AND C OMPUTER S CIENCES ,
    N ICOLAUS C OPERNICUS U NIVERSITY IN T ORU Ń
    UL . G AGARINA 11, 87-100 T ORU Ń , P OLAND
    AND
    I NSTITUTE OF M ATHEMATICS ,
    P OLISH ACADEMY OF S CIENCES ,
    UL . Ś NIADECKICH 8, 00-656 WARSAW, P OLAND


    Email address: jsiem@mat.umk.pl
