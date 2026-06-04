## Biharmonic nonlinear scalar field equations

Jarosław Mederski and Jakub Siemianowski


ABSTRACT. We prove a Brezis-Kato-type regularity result for weak solutions to the biharmonic nonlinear
equation
∆ [2] u = g(x, u) in R [N]

with a Carathéodory function g : R [N] × R → R, N ≥ 5. The regularity results give rise to the existence
of ground state solutions provided that g has a general subcritical growth at infinity. We also conceive a new
biharmonic logarithmic Sobolev inequality

    -    -    -    -    



  -  C
8 [log]




    -    , for u ∈ H [2] (R [N] ),
R [N] [|][∆][u][|][2][ dx]



R [N] [|][u][|][2][ log][ |][u][|][ dx][ ≤] [N] 8




        - �2
for a constant 0 < C < πeN2 and we characterize its minimizers.



R [N] [u][2][ dx][ = 1][,]



1. Introduction


The study of higher-order differential elliptic operators is important, e.g. in nonlinear elasticity [3], low
Reynolds number hydrodynamics, in structural engineering [21, 24] as well as in nonlinear optics [11], and
has attracted attention from the mathematical point of view [12]. The methods developed for the second
order problem, e.g. involving the Laplacian −∆, may no longer be available. For instance, it is the wellknown that the bi-Laplacian (−∆) [2] = ∆ [2] cannot be studied by means of some classical methods such
as maximum principles, Polya-Szeg˝o inequalities, or even if (∆u) [2] ∈ L [1] (R [N] ), then it is possible that
∆|u| ∈/ L [1] loc [(][R][N] [)][.]
The first aim is of this work is to establish a regularity result in the spirit of Brezis-Kato [6] of weak
solutions to

(1.1) ∆ [2] u = g(x, u), x ∈ Ω,

where Ω ⊂ R [N] is a domain, N ≥ 2 and g : Ω × R → R is a Carathéodory function. If we suppose that Ω is
bounded, then there is an extensive literature devoted to this problem. Namely, recall that if g(x, u) = f (x),
then Agmon, Douglis, Nirenberg [2] showed that for 1 < q < ∞, f ∈ L [q] (Ω), there exists a unique strong
solution u ∈ W0 [2][,][2][(Ω)][∩][W][ 4][,q][(Ω)][ to (][1.1][) provided that][ ∂][Ω] [∈] [C] [4][ see also [][12][, Corollary 2.21] and references]
therein. Recently Mayboroda and Maz’ya [17] showed L [∞] -estimates of u (resp. ∇u), where f ∈ C0 [∞][(Ω)][,]
Ω is an arbitrary bounded domain and N = 4, 5 (resp. N = 2, 3). To the best of our knowledge, a variant
of Brezis-Kato result [6] for (1.1) is known only on a bounded domain in a particular case. Namely, Van
der Vorst [25] showed that, if N ≥ 5, g(x, u) = a(x)u and a(x) ∈ L [N/][4] (Ω), then any weak solution
u ∈ W0 [1][,][2][(Ω)][ ∩] [W][ 2][,][2][(Ω)] [to] [(][1.1][) satisfies] [u] [∈] [L][q][(Ω)][ for] [all] [1] [≤] [q] [<] [∞][.] [This] [result] [is] [suitable] [to show]
the regularity for the biharmonic equation with the nonlinearities of the special form g(x, u) = f (u)u cf.

[25, Lemma B3]. In this paper we give a full answer to the problem on an arbitrary domain and for general
g with the adequate Brezis-Kato growth as we shall see below.


2000 Mathematics Subject Classification. 35J91,35J20.
Key words and phrases. Nonlinear scalar field equation, Brezis-Kato reqularity, biharmonic logarithmic Sobolev inequality,
critical point theory, Pohozaev manifold.

1


2 J. MEDERSKI AND J. SIEMIANOWSKI



From now on we assume that Ω ⊂ R [N] possibly unbounded domain and N ≥ 5. Inspired by [6], we
impose on g the following growth assumption:

             -              (1.2) |g(x, s)| ≤ a(x) 1 + |s|, for s ∈ R and a.e. x ∈ Ω, where 0 ≤ a ∈ L [N/] loc [4][(Ω)][.]

The first main result reads as follows.

THEOREM 1.1. Let u ∈ Wloc [2][,][2][(Ω)] [be] [a] [weak] [solution] [to] [(][1.1][)][,] [where] [g] [satisfies] [(][1.2][)][.] [Then] [u] [∈]
Cloc [3][,α][(Ω)][ ∩] [W][ 4] loc [,q][(Ω)][, for any][ 0][ < α <][ 1][ and][ 1][ ≤] [q] [<][ ∞][.]


It is worth mentioning that in proof of Theorem 1.1 we can no longer apply classical techniques for
Laplacian, e.g. due to Brezis and Kato [6], or Brezis and Lieb [7, Theorem 2.3], since ∆|u| may not be
well-defined for u ∈ Wloc [2][,][2][(Ω)][.] [Moreover,] [the] [Moser] [iteration] [technique] [does] [not] [seem] [to] [be] [applicable]
straightforwardly for g.
We shall present some consequences of Theorem 1.1 in Ω= R [N] . Let us define D [2][,][2] (R [N] ) as a comple
��                 - 21
tion of the space C0 [∞][(][R][N] [)] [with respect] [to] [the] [norm] [∥][u][∥] D [2][,][2] [:=] |α|=2 [∥][∂][α][u][∥][2] L [2] (R [N] ) . By the use of

the Fourier transform and the Plancharel theorem we find a constant c > 0 such that, for u ∈ C0 [∞][(][R][N] [)][,]
1

[≤∥][∆][u][∥][L][2][(][R][N] [)] [≤] [c][∥][u][∥][D][2][,][2][(][R][N] [)][.]
c [∥][u][∥][D][2][,][2][(][R][N][ )]

Therefore, the norms ∥u∥ := ∥∆u∥L2(RN ) and ∥u∥D2,2(RN ) are equivalent on D [2][,][2] (R [N] ). Moreover,
D [2][,][2] (R [N] ) is a Hilbert space with the inner product




    ⟨u, v⟩ :=



for u, v ∈D [2][,][2] (R [N] )
R [N] [∆][u][∆][v dx]



and u ∈D [2][,][2] (R [N] ) is a weak solution to (1.1) provided that




    ⟨u, v⟩ =



for any v ∈ C0 [∞][(][R][N] [)][.]
R [N] [g][(][x, u][)][v]



As usually expected, the following general Pohožaev-type result holds, cf. [23].



THEOREM 1.2. Let u ∈D [2][,][2] (R [N] ) be a weak solution to (1.1), where g satisfies (1.2). Then




      
(1.3)



2N
R [N] [|][∆][u][|][2][ dx][ =] N - 4



2
R [N] [G][(][x, u][)][ dx][ +] N - 4











R [N] [x][ ·][ ∂][x][G][(][x, u][)][ dx.]




                             s
provided that G(x, u), x · ∂xG(x, u) ∈ L [1] (R [N] ), where G(x, s) := 0 [g][(][x, t][)][ dt][,][ x][ ∈] [R][N] [,][ t][ ∈] [R][.]



We demonstrate that the Brezis-Kato result for biharmonic Laplacean as well as Theorem 1.2 open
the way to study the existence of solutions and their regularity for (1.1). Indeed, let us assume that g is
independent of x and the following condition holds:

                        (g0) there is a constant c > 0 such that |g(s)| ≤ c 1 + |s| [2][∗∗][−][1][�] for s ∈ R,

where 2 [∗∗] := N2N−4 [.] [Then] [a][(][x][)] [:=] [g][(][u][(][x][))][/][(1] [+][ |][u][(][x][)][|][)] [∈] [L][N/] loc [4][(][R][N] [)] [for] [u] [∈] [L][2][∗∗][(][R][N] [)] [and] [in] [view]
of Theorem 1.1, weak solutions to the semilinear problem (1.1) belong to Cloc [3][,α][(][R][N] [)] [∩] [W][ 4] loc [,q][(][R][N] [)][.] [We]
introduce the energy functional



(1.4) J(u) := [1]







2




     R [N] [|][∆][u][|][2][ −]



R [N] [G][(][u][)][ dx,]




       - s
where G(s) = [Next, we show the existence of weak solutions to (][1.1][) under growth assumption]
0 [g][(][t][)][ dt][.]
at 0 and at infinity inspired by a seminal paper due to Berestycki and Lions [5] (cf. [19, 20]). We assume
that g is continuous, g(0) = 0 and (g0) holds. Let



G+(s) :=



�� s
for s ≥ 0,
�0 [max][{][g][(][t][)][,][ 0][}][ dt]
0
s [max][{−][g][(][t][)][,][ 0][}][ dt] for s < 0,


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 3


and g+(s) = G [′] + [(][s][)][.] [Suppose in addition, that and the following conditions are satisfied:]

(g1) lims→0 G+(s)/|s| [2][∗∗] = 0,
(g2) there exists ξ0  - 0 such that G(ξ0) > 0,
(g3) lim|s|→∞ G+(s)/|s| [2][∗∗] = 0.



We introduce the Pohožaev manifold

         -         (1.5) M := u ∈D [2][,][2] (R [N] ) \ {0} :




      -       
[= 2][∗∗],
R [N] [|][∆][u][|][2] R [N] [G][(][u][)][ dx]




      
[= 2][∗∗]
R [N] [|][∆][u][|][2]



and in view of Theorem 1.2, M contains all nontrivial solutions. The existence result reads as follows.


THEOREM 1.3. Let (g0)–(g3) be satisfied. Then infM J  - 0 and there is a ground state solution u0 ∈
D [2][,][2] (R [N] ) to (1.1), i.e. u0 ∈M solves (1.1) and J(u0) = infM J. Moreover u0 ∈ Cloc [3][,α][(][R][N] [)][ ∩] [W][ 4] loc [,q][(][R][N] [)][,]
for any 0 < α < 1 and 1 ≤ q < ∞.


Theorem 1.3 enables us to consider the following nonlinearity


(1.6) G(s) = s [2] log |s| for s ̸= 0, and G(0) = 0


which satisfies (g0)–(g3). In view of Theorem 1.3 there is a ground state solution to (1.1) and



CN,log := 2 [∗∗][�] [1]



2 [∗∗]




[1]

2 [−] 2 [1]



�− N4−4 N4−4
(inf .
M [J][)]



We gain the following new biharmonic logarithmic Sobolev inequality.




                     THEOREM 1.4. For any u ∈D [2][,][2] (R [N] ) such that



R [N] [|][u][|][2][ dx][ = 1][, there holds]




 ≥

R [N] [|][u][|][2][ log][ |][u][|][ dx]







N
(1.7)

8 [log]



��
8e
CN,log(N  - 4)



�(N −4)/N 
R [N] [|][∆][u][|][2][ dx]



and

         8e
CN,log(N               - 4)



�(N −4)/N 2
<
πeN



�2
.



Moreover the equality in (1.7) holds provided that u = u0/∥u0∥L2(RN ) and u0 is a ground state solution
to (1.1). If the equality in (1.7) holds for u, then there are uniquely determined λ - 0 and r - 0 such that
u0 := λu(r·) ∈M and u0 is a ground state solution to (1.1).



Recall that the classical logarithmic Sobolev inequality given in [26]:




               for u ∈ H [1] (R [N] ),
R [N] [|][u][|][2][ log(][|][u][|][)][ dx,]




    -     ≥
R [N] [|∇][u][|][2][ dx]



R [N] [|][u][|][2][ dx][ = 1][,]




      
N 2
(1.8)

4 [log] πeN







which is equivalent to the Gross inequality [13], cf. [14]. Recall that the optimality of (1.8) and the characterization of minimizers have been already proved by Carlen [8] in the context of the Gross inequality as
well as by del Pino and Dolbeault [9, 10] for the interpolated Gagliardo–Nirenberg inequalities and the L [p] Sobolev logarithmic inequality. A generalization of the optimal Gross inequality in Orlicz spaces is given
by Adams [1]. However, to the best of our knowledge, the logarithmic Sobolev inequality for higher order
operators have not been obtained in the literature so far and (1.8) seems to be the first one for the biharmonic
Laplacian. Note that, in contrast to (1.8) and the Laplacian problem involving (1.6), we do not know ground
state solutions to (1.1) explicitly. Hence the exact computation of CN,log remains an open question.
The paper is organized as follows. In Section 2 we prove Theorem 1.1 and in Section 3 we obtain the
Pohožaev-type result. The main result of Section 4 is a general variant of Lion’s lemma (Lemma 4.1) in
D [2][,][2] (R [N] ), which is crucial for the proof of Theroem 1.3 given in Section 5. The last Section 6 is devoted to
the biharmonic logarithmic Sobolev inequality.


4 J. MEDERSKI AND J. SIEMIANOWSKI


2. Regularity theory and proof of Theorem 1.1



Let N, k ∈ N and 1 ≤ p < ∞ with N   - kp. We define D [k,p] (R [N] ) as a completion of the space
C0 [∞][(][R][N] [)][ with respect to the norm]














1
p
, u ∈ C0 [∞][(][R][N] [)][.]



∥u∥Dk,p :=



 [�] ∥D [α] u∥ [p] L [p] (R [N] )

|α|=k



Hence


Np
(2.1) D [k,p] (R [N] ) ⊂D [k][−][l,] N−lp (R [N] ), 0 ≤ l ≤ k,


and




 
∥D [α] u∥ Np u ∈D [k,p] (R [N] ).
L N−jp (RN ) [≤] [c][∥][u][∥][D][k,p][,]
|α|=k−j



(2.2)



�k


j=0



We fix an open set Ω ⊂ R [N] . We recall that by the standard approach based on mollifiers and the
Calderon–Zygmund L [p] –estimates for higher order elliptic operators [22, (2.6)] we have the following
lemma.

LEMMA 2.1. Let 1 < p < ∞ and k be a positive integer. If w ∈ L [p] loc [(Ω)] [and] [∆][k][w] [∈] [L][p] loc [(Ω)][,] [then]
w ∈ Wloc [2][k,p][(Ω)][.]

Suppose that u ∈ Wloc [2][,][2][(Ω)][ is a weak solution to (][1.1][), where][ g][ satisfies (][1.2][). Clearly][ u][ ∈] [L] loc [2][∗∗][(Ω)][.] [Fix]
U ⊂⊂ Ω. Since 2N [N] 2N
N +4 [<] 4 [and] N +4 [= 2][∗∗] N [N] +4 [−][4] [, by the Hölder inequality]



2N
4 [and] N +4 [= 2][∗∗] N [N] +4 [−][4]



N +4 [<] 4 [and] N +4 [= 2] N +4 [, by the Hölder inequality]

- 



        2N
|g(x, u)| N+4 dx ≤ c
U



2N N
|a(x)| N+4 + |a(x)| 4
U



8
4 N+4 N+4
|u| [2][∗∗] [N][−][4]



N+4 dx < ∞,



for some constant c > 0. Then, by the distributional equality



∆ [2] u = g(x, u) ∈ L

and Lemma 2.1, we infer that u ∈ Wloc4, N [2][N] +4 (Ω).

Now the crucial step is the following lemma.



2N
locN+4 (Ω),



2N
LEMMA 2.2. Let p ≥ N +4 [and][ u][ ∈] [W][ 4] loc [,p][(Ω)][ be a weak solution to][ (][1.1][)][, where][ g][ satisfies][ (][1.2][)][.] [Then]



u ∈




L [Np/N] loc [−][5][p] (Ω), if 5p < N,
L [q] loc [(Ω)] [for every][ 1][ ≤] [q] [<][ ∞][,] if 5p ≥ N.



PROOF. If 4p ≥ N, then the conclusion follows immediately by the Sobolev embedding Wloc [4][,p][(Ω)] [⊂]
L [q] loc [(Ω)][,][ q] [≥] [1][.] [Thus, we can clearly assume that][ 4][p < N] [.] [Let us define]



a˜(x) :=




g(x,u(x))
u(x) χ{x∈Ω||u(x)|>1}(x), for u(x) ̸= 0,



0 for u(x) = 0,



b(x) := g(x, u(x))χ{x∈Ω||u(x)|≤1}(x),

and observe that g(x, u) = ˜a(x)u + b(x) and ˜a, b ∈ L [N/] loc [4][(Ω)][.]
Let U be an arbitrary open bounded subset of Ω such that U ⊂ U ⊂ Ω. We find an open bounded
V with C [∞] -smooth boundary such that U ⊂ V ⊂ V ⊂ Ω. Indeed, let ξ ∈ C0 [∞][(Ω)] [be] [a] [smooth] [cut-off]
function such that ξ ≡ 1 on U and 0 ≤ ξ ≤ 1. By Sard’s theorem, there is a regular value c ∈ (0, 1).
Then V = ξ [−][1] ((c, 1]) is an open bounded subset with the smooth boundary ∂V = ξ [−][1] ({c}) satisfying
U ⊂ V ⊂ V ⊂ Ω.


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 5


Now take η ∈ C0 [∞][(][V][ )] [such] [that] [η] [=] [1] [on] [U] [and] [0] [≤] [η] [≤] [1][.] [We] [restrict] [our] [problem] [to] [V][ .] [By] [the]
assumption u ∈ W [4][,p] (V ) is a distributional solution of

(2.3) ∆ [2] u = ˜a(x)u + b(x) in V

and ˜a, b ∈ L [N/][4] (V ). We define
v := uη.
Certainly, we have v ∈ W [4][,p] (V ) ⊂ H [2] (V ) and v ∈ H0 [1][(][V][ )][,] [since] [supp][ η] [⊂⊂] [V][ .] [Standard] [calculations]
yield




     ∆ [2] v = (∆ [2] u)η + 4∇∆u · ∇η + 4



(2.4)




- �� =:K(u)



∇uxi   - ∇ηxi + 2∆u∆η + 4∇u · ∇∆η + u∆ [2] η
i=1 [N]



=: (∆ [2] u)η + K(u).

Observe that u ∈ W [4][,p] (V ) ⊂ W [3][,p][∗] (V ), p [∗] = NNp−p [and][ η] [∈] [C] 0 [∞][(][V][ )][ imply that]

(2.5) ∥K(u)∥Lp [∗] (V ) ≤ c∥u∥W 3,p [∗] (V )∥η∥W 4,∞(V ) ≤ c(η)∥u∥W 4,p(V ),


for some constant c(η) > 0.
In view of [25, Lemma B.2], for every ε > 0 there are qε ∈ L [N/][4] (V ) and f [�] ε ∈ L [∞] (V ) such that

(2.6) a˜(x)v = qε(x)v + f [�] ε,


and


(2.7) ∥qε∥LN/4(V ) ≤ ε.


By (2.4), (2.3) and (2.6) we get

∆ [2] v = (∆ [2] u)η + K(u)



(2.8)


where



= ˜a(x)v + b(x)η + K(u)

= qε(x)v + fε + K(u),



N
(2.9) fε := f [�] ε + b(x)η ∈ L 4 (V ).

We recall some needed regularity results from [2] (see also [12, Thm 2.20]), for all 1 < q < ∞,
g¯ ∈ L [q] (V ), there exists a unique strong solution u ∈ W [4][,q] (V ) to the problem

          (−∆) [2] u = g¯ in V,
u = ∆u = 0 on ∂V.


satisfying
∥u∥W 4,q(V ) ≤ cq∥g¯∥Lq(V ),
where cq - 0 depends only on N, q and V . Denote by Tq the linear operator g �→ u considered as an
operator from L [q] (V ) to W [4][,q] (V ) and rewrite the above inequality as


(2.10) ∥Tqg¯∥W 4,q(V ) ≤ cq∥g¯∥Lq(V ).

Obviously, Tq is the L [q] -inverse of the bilaplacian (−∆) [2] considered with the Navier boundary conditions
u = ∆u = 0 on ∂V .
Now we can rephrase (2.8) in the language of operators


(2.11) v − Aε,qv = hε,q,

where Aε,qv := Tq(qεv) and hε,q := Tq(fε + K(u)).
We consider two cases separately.


6 J. MEDERSKI AND J. SIEMIANOWSKI


Case I: 5p < N .


Np

In what follows we take q = p [∗] . By the Sobolev embedding W [4][,p][∗] (V ) ⊂ L N−5p (V ), (2.10), (2.9) and

(2.5), we have

∥hε,p [∗] ∥L NNp−5p (V ) [≤] [c][Sobolev][∥][T][p][∗] [(][f][ε][ +][ K][(][u][))][∥][W][ 4][,p][∗] [(][V][ )]



≤ cSobolevcp [∗] ∥fε + K(u)∥Lp [∗] (V )







(2.12)




 ≤ c ∥fε∥ N
L 4

 ≤ c ∥fε∥ N
L 4



4 (V ) [+][ ∥][K][(][u][)][∥][L][p][∗] [(][V][ )]



4 (V ) [+][ c][(][η][)][∥][u][∥][W][ 4][,p][(][V][ )]




,



Np
N−5p
(V )



where c > 0 is some constant. We estimate the norm of the linear operator Aε,p [∗] : L



Np
N−5p
(V ) → L



applying the Sobolev embedding W [4][,p][∗] (V ) ⊂ L



Np
N−5p (V ) and (2.10)



(2.13) ∥Aε,p [∗] v∥L NNp−5p (V ) [≤] [c][Sobolev][∥][T][p][∗][(][q][ε][v][)][∥][W][ 4][,p][∗] [(][V][ )] [≤] [c][Sobolev][c][p][∗][∥][q][ε][v][∥][L][p][∗] [(][V][ )][.]


We use the Hölder inequality with the exponents



1
N



p [∗]



1 1

+ = [1]

N Np p [∗]

4 N −5p



to obtain


(2.14) ∥qεv∥Lp [∗] (V ) ≤∥qε∥LN/4(V )∥v∥L NNp−5p (V ) [.]


In view of (2.13), (2.14) and (2.7) we gain

∥Aε,p [∗] v∥L NNp−5p (V ) [≤] [c][Sobolev][c][p][∗][ε][∥][v][∥] L NNp−5p (V ) [.]

We choose ε := (2cSobolevcp [∗] ) [−][1] to deduce

(2.15) ∥Aε,p [∗] ∥L NNp−5p →L NNp−5p [≤] [1] 2 [.]



Then (I − Aε,p [∗] ) is invertible on the space L



Np
N−5p (V ) with the norm bounded by 2 and by (2.11)



(2.16) v = (I - Aε,p [∗] ) [−][1] hε,p [∗],


so by the above and by (2.12)

∥v∥L NNp−5p (V ) [≤] ���(I − Aε,p∗)−1���L NNp−5p →L NNp−5p [∥][h][ε,p][∗][∥] L NNp−5p (V )

                  -                  ≤ 2c ∥fε∥L∞(V ) + c(η)∥u∥W 4,p(V ) < ∞.



Hence v ∈ L NNp−5p (V ) and, since u = v on U ⊂ Ω and U is arbitrary, we finally get u ∈ LlocNNp−5p (Ω) as

claimed. This finishes the proof of Case I.



Hence v ∈ L



Np
N−5p (V ) and, since u = v on U ⊂ Ω and U is arbitrary, we finally get u ∈ L



Case II: 5p ≥ N .



Np Nq
We proceed similarly as in Case I. Fix any N −4p [≤] [q] [<] [∞] [and] [define] [r] [:=] N +4q [.] [Then] [we] [have]



Np
4 [≤] N −p [.] [We] [employ] [the] [Sobolev] [embedding] [W][ 4][,r][(][V][ )] [⊂] [L][q][(][V][ )][,] [(][2.10][),] [(][2.9][)] [and] [(][2.5][)] [to]



1 < r < [N]


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 7



estimate


(2.17)




 ≤ c ∥fε∥ N
L 4

 ≤ c ∥fε∥ N
L 4




      

N

4 (V ) [+][ ∥][K][(][u][)][∥][L][p][∗]



∥hε,r∥Lq(V ) ≤ cSobolev∥Tr(fε + K(u))∥W 4,r (V )
≤ cSobolevcr∥fε + K(u)∥Lr(V )




,



N

4 (V ) [+][ c][(][η][)][∥][u][∥][W][ 4][,p] [(][V][ )]



for some constant c - 0. We bound the norm of Aε,r : L [q] (V ) → L [q] (V ) by exploiting the Sobolev
embedding W [4][,r] (V ) ⊂ L [q] (V ) and (2.10)


(2.18) ∥Aε,r∥Lq(V ) ≤ cSobolev∥Tr(qεv)∥W 4,r(V ) ≤ cSobolevcr∥qεv∥Lr(V ).



We use Hölder’s inequality with exponents

1
N



1 1

+
Nr
4 ����N −4r
= [1]



= [1]

r



q



and (2.7) to obtain

(2.19) ∥qεv∥Lr (V ) ≤∥qε∥L N4 (V ) [∥][v][∥][L][q][(][V][ )] [≤] [ε][∥][v][∥][L][q] [(][V][ )][.]

We choose ε = (2cSobolevcr) [−][1] and from (2.18), (2.19) deduce that

∥Aε,r∥Lq→Lq ≤ [1]

2 [.]

As in the last part of Case I, we then show that v ∈ L [q] (V ). This implies that u ∈ L [q] (U ) and, since U ⊂ Ω
and q ≥ NNp−4p [were arbitrary, the proof of Case II is completed.] 


Proof of Theorem 1.1. Let u ∈ Wloc [2][,][2][(Ω)] [be] [a] [weak] [solution] [to] [(][1.1][).] [Then] [u] [∈] [W] loc4, N [2][N]



Proof of Theorem 1.1. Let u ∈ Wloc [(Ω)] [be] [a] [weak] [solution] [to] [(][1.1][).] [Then] [u] [∈] [W] locN+4 (Ω). We show

that u ∈ L [q] loc [(Ω)][,] [for] [every] [q] [≥] [1][.] [If] [N] [=] [5] [or] [N] [=] [6][,] [then,] [by] [Lemma] [2.2][,] [u] [∈] [L][q] loc [(Ω)][,] [for] [every]
q ≥ 1, and we are done. If N - 6, then we define p1 := N2N+4 [,][ 5][p][1] [<] [N] [, and we use Lemma][ 2.2][ to obtain]



Np1
locN−5p1 (Ω). Since NNp−51p1 [=] N2N−6 [,]



u ∈ L



Np1
p1 < p2 :=
N    - 5p1



N - 6 2N [N]
N + 2 [=] N + 2 [<] 4 [.]



Fix U ⊂⊂ Ω. Observe that p2 [N] [+2]



⊂⊂ Ω. Observe that p2 8 = 4 [and by the Hölder inequality]

- - [�]



|a(x)| [p][2][ N] 8 [+2]
U




  - 8
8 [+2] dx N+2 [��]




        |g(x, u)| [p][2] dx ≤ c
U




      - [�]
|a(x)| [p][2] dx + c
U




[+2] = [N]

8 4



|u|
U



NNp−51p1 dx� [N] N [−] +2 [6] < ∞



for some constant c > 0. Therefore we get ∆ [2] u = g(x, u) ∈ L [p] loc [2] [(Ω)][.] [Since][ u][ ∈] [W][ 4] loc [,p][1][(Ω)] [⊂] [L][p] loc [2] [(Ω)][, we]
use Lemma 2.1 to get u ∈ Wloc [4][,p][2][(][R][N] [)][.] [Let][ K] [be the] [largest] [natural] [number] [less] [than] [N] 2 [−][4] [.] [We continue]

applying Lemma 2.2 in this fashion and get a finite sequence (pk) [K] k=1 [such that for][ k] [= 1][, ..., K]

2N
pk :=
N + 6 − 2k [,]



N + 6 − 2k
pk



4 [,]



 - 2k

= [N]
8 4



Npk
pk+1 =
N   - 5pk



N - 4 − 2k
if k ≥ 1.
N + 4 − 2k [,]


8 J. MEDERSKI AND J. SIEMIANOWSKI



NpK

By the definition of K, we get 5pK < N, NNp−5KpK [≥] [N] [and][ u] [∈] [L] locN−5pK (Ω). Finally, by Lemma 2.2 we

obtain that u ∈ L [q] loc [(Ω)][,] [for] [every] [q] [≥] [1][.] [Since] [∆][2][u] [=] [g][(][x, u][)] [∈] [L][q] loc [(Ω)][,] [for] [every] [1] [≤] [q] [<] [∞][,] [by]
Lemma 2.1, u ∈ Wloc [4][,q][(Ω)][,][ q] [≥] [1][, so by the Sobolev embedding][ u][ ∈] [C] loc [3][,α][(Ω)][, for every][ 0][ < α <][ 1][.] 

3. Pohožaev identity


Proof of Theorem 1.2. One can find ϕ ∈ C [∞] (R) satisfying ϕ|(−∞,1] ≡ 1, ϕ|[2,∞) ≡ 0 and 0 ≤ ϕ ≤ 1. For



�(

x| [2]

.
n [2]




                   |x| [2]
every n ≥ 1, we define ϕn ∈ C0 [∞][(][R][N] [)][ by][ ϕ][n][(][x][) :=][ ϕ] n [2]



By Theorem 1.1, we may assume that u ∈ Cloc [3][,α][(][R][N] [)][ ∩] [W][ 4] loc [,q][(][R][N] [)][,][ 0][ < α <][ 1][,][ 1][ ≤] [q] [<][ ∞][, so]

0 = ∆ [2] u − g(x, u) a.e. in R [N] .

Thus, for a.e. x ∈ R [N] and for every n, we obtain

(3.1) 0 = (∆ [2] u − g(x, u))ϕnx · ∇u.


The following identities hold


g(x, u)ϕnx · ∇u = div (ϕnG(x, u)x) − G(x, u)x · ∇ϕn − NϕnG(x, u) − ϕnx · ∂xG(x, u)


and

∆ [2] uϕnx · ∇u = div (ϕn(x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − ϕn∇(x · ∇u) · ∇(∆u).


We transform the rightmost term of the above equation


ϕn∇(x · ∇u) · ∇(∆u) = −ϕn∆u∆(x · ∇u) + ϕndiv (∆u∇(x · ∇u))

= −ϕn∆u(2∆u + x · ∇∆u) + div (ϕn∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u)

= −2ϕn(∆u) [2]         - ϕn∆ux · ∇∆u + div (ϕn∆u∇(x · ∇u)) − ∆u∇ϕn · ∇(x · ∇u).



Finally, we rewrite the second term of the above line as follows




      (∆u) [2]
ϕn∆ux · ∇∆u = div ϕn




[1]

2 [(∆][u][)][2][∇][ϕ][n][ ·][ x][ −] [N] 2




  
u) [2]

x  - [1]
2 2



2 [ϕ][n][(∆][u][)][2][.]



Putting the above identities into (3.1) we get



0 = −div (ϕnG(x, u)x) + G(x, u)x · ∇ϕn + NϕnG(x, u) + ϕnx · ∂xG(x, u)



��

[u][)][2]

x
2




                + div (ϕn(x · ∇u)∇∆u) − (x · ∇u)(∇ϕn · ∇∆u) − div ϕn




∆u∇(x · ∇u) − [(∆][u][)][2]




[−] [4]

- [N]



2 [(∆][u][)][2][x][ · ∇][ϕ][n][ + ∆][u][∇][ϕ][n][ · ∇][(][x][ · ∇][u][)]




[−] [4]

ϕn(∆u) [2]  - [1]
2 2



or, equivalently,

   (3.2) div ϕn




- ��
G(x, u)x + ∆u∇(x · ∇u) − x · ∇u∇∆u − [(∆][u][)][2] x

2



= G(x, u)x · ∇ϕn + NϕnG(x, u) + ϕnx · ∂xG(x, u) − (x · ∇u)(∇ϕn · ∇∆u)




[−] [4]

- [N]



2 [(∆][u][)][2][x][ · ∇][ϕ][n][ + ∆][u][∇][ϕ][n][ · ∇][(][x][ · ∇][u][)][.]




[−] [4]

ϕn(∆u) [2]  - [1]
2 2



Fix n ≥ 1 and take R > 0 such that supp ϕn ⊂ BR. By the divergence theorem, we obtain




  0 =



G(x, u)x · ∇ϕn + NϕnG(x, u) + ϕnx · ∂xG(x, u) − (x · ∇u)(∇ϕn · ∇∆u)
BR




[−] [4]

- [N]



2 [(∆][u][)][2][x][ · ∇][ϕ][n][ + ∆][u][∇][ϕ][n][ · ∇][(][x][ · ∇][u][)][ dx.]




[−] [4]

(∆u) [2] ϕn − [1]
2 2


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 9



Note that




           (x·∇u)(∇ϕn·∇∆u) dx =
BR




                ∆u∇ϕn·∇(x·∇u)+∆u∆ϕnx·∇u dx− div (x · ∇u∆u∇ϕn)
BR - BR �� 
=0




 



dx.



Summing up, we have
(3.3)




  0 =



G(u)x · ∇ϕn + NϕnG(x, u) + ϕnx · ∂xG(x, u) + 2∆u∇ϕn · ∇(x · ∇u) + ∆u∆ϕnx · ∇u
BR




[−] [4]

- [N]



2 [(∆][u][)][2][x][ · ∇][ϕ][n][ dx]




 =




[−] [4]

(∆u) [2] ϕn − [1]
2 2



R [N] [G][(][u][)][x][ · ∇][ϕ][n][ +][ Nϕ][n][G][(][x, u][) +][ ϕ][n][x][ ·][ ∂][x][G][(][x, u][) + 2∆][u][∇][ϕ][n][ · ∇][(][x][ · ∇][u][) + ∆][u][∆][ϕ][n][x][ · ∇][u]




[−] [4]

- [N]



2 [(∆][u][)][2][x][ · ∇][ϕ][n][ dx.]




[−] [4]

(∆u) [2] ϕn − [1]
2 2



We return to (3.3) and pass to the limit as n →∞ to obtain




   0 = N




       R [N] [G][(][x, u][)][ dx][ +]




[−] [4]
R [N] [x][ ·][ ∂][x][G][(][x, u][)][ dx][ −] [N] 2



2





R [N] [|][∆][u][|][2][ dx,]



where we used Lebesgue’s dominated convergence theorem and the properties of ϕn. The proof is completed. 

4. Lions lemma


We prove a biharmonic variant of Lion’s lemma, cf. [15, 16], [20, Section 2].


LEMMA 4.1. Suppose that (un) is bounded in D [2][,][2] (R [N] ) and for some r > 0

                  


(4.1) lim
n→∞ y [sup] ∈R [N]


Then 


|un| [2] dx = 0.
B(y,r)



as n →∞
R [N] [Ψ(][u][n][)][ dx][ →] [0]

for every continuous Ψ : R → R satisfying


Ψ(s) Ψ(s)
(4.2) lim [lim]
s→0 |s| [2][∗∗] [=] |s|→∞ |s| [2][∗∗] [= 0][.]


We prove the following result, which implies the variant of Lions’s lemma in D [2][,][2] (R [N] ).


LEMMA 4.2. Suppose that (un) ⊂D [2][,][2] (R [N] ) is bounded. Then un(· + yn) ⇀ 0 in D [2][,][2] (R [N] ) for any
(yn) ⊂ Z [N] if and only if 
as n →∞
R [N] [Ψ(][u][n][)][ dx][ →] [0]

for any continuous Ψ : R → R satisfying (4.2).


PROOF. Let (un) be a sequence in D [2][,][2] (R [N] ) be such that un(· + yn) ⇀ 0 in D [2][,][2] (R [N] ) for every
(yn) ⊂ Z [N] . Take any ε > 0 and 2 [∗] < p < 2 [∗∗] and suppose that Ψ satisfies (4.2). Then we find 0 < δ < M
and c(ε) > 0 such that

Ψ(s) ≤ ε|s| [2][∗∗] for |s| ≤ δ,

Ψ(s) ≤ ε|s| [2][∗∗] for |s| > M,
Ψ(s) ≤ c(ε)|s| [p] for |s| ∈ (δ, M ].


10 J. MEDERSKI AND J. SIEMIANOWSKI



Let us define (wn) by



wn(x) :=




|un(x)| for |un(x)| > δ,
|un(x)| [2][∗∗][/][2][∗] δ [1][−][2][∗∗][/][2][∗] for |un(x)| ≤ δ.



We are about to show that (wn) is bounded in W [1][,][2][∗] (R [N] ). First of all, we have




       R [N] [|][w][n][(][x][)][|][2][∗] [dx][ =]




           δ [2][∗][−][2][∗∗] |un| [2][∗∗] dx +
{|un|≤δ}




        |un| [2][∗∗] dx +
{|un|≤δ}

        |un| [2][∗∗] dx +
{|un|≤δ}







|un| [2][∗] dx
{|un|≥δ}



|un| [2][∗∗]

|un| [2][∗∗][−][2][∗] [dx]



(4.3)



= δ [2][∗][−][2][∗∗] [�]

≤ δ [2][∗][−][2][∗∗] [�]

= δ [2][∗][−][2][∗∗] [�]



{|un|>δ}



{|un|>δ}



|un| [2][∗∗]

δ [2][∗∗][−][2][∗] [dx]



R [N] [|][u][n][|][2][∗∗] [dx.]



By the absolute continuous characterization (see §1.1.3 in [18]), we infer that each un is absolutely continuous on almost every line parallel to the 0xi-axis, for i = 1, . . ., N . Thus the same holds for each wn, since
wn = F (un), where F (t) = min{δ [1][−][2][∗∗][/][2][∗] |t| [2][∗∗][/][2][∗], |t|} is a globally Lipschitz function. Moreover, for
every i = 1, . . ., N, we have



∂wn

=
∂xi



∂wn




2 [∗∗]



2 [∗] [δ][1][−][2] [/][2] [sign(][u] [n][)][|][u] [n][|][2] [/][2] [−][1] ∂x [n] i [,] for |un(x)| ≤ δ,

sign(un) [∂u][n] for |un(x)| > δ.

[,]




[∗∗]

2 [∗] [δ][1][−][2][∗∗][/][2][∗] [sign(][u][n][)][|][u][n][|][2][∗∗][/][2][∗][−][1][ ∂u] ∂x [n] i



∂x [n] i [,] for |un(x)| > δ.



Thus


(4.4)



2 [∗]



2 [∗]
dx

����



����




 2∗∗
≤

2 [∗]




 2∗∗
≤

2 [∗]

 2∗∗
≤

2 [∗]






R [N]



∂wn
����

∂xi



2 [∗] - 2∗∗
dx =



�2∗
δ [2][∗][−][2][∗∗] [�]


�2∗ 


∂un
|un| [2][∗∗][−][2][∗] [���]     {|un|≤δ} ∂xi



∂un
����



����



∂un
����

∂xi



2 [∗] dx +



∂un
����

∂xi



{|un|>δ}



����



{|un|>δ}



∂xi



2 [∗]
dx



����



2 [∗] dx +



∂xi




 2∗∗
≤



{|un|≤δ}



�2∗ 


����



2 [∗]
dx.



R [N]



∂un
����



∂xi



By (4.3), (4.4) (again using an absolute continuous characterization on lines from §1.1.3 [18]) and the fact
that (un) is bounded in D [2][,][2] (R [N] ), we conclude that (wn) is bounded in W [1][,][2][∗] (R [N] ).
Let Ω= (0, 1) [N] and y ∈ R [N] be arbitrary. Then, by the Sobolev inequality one has

 - - 



        Ψ(un) dx =
Ω+y




            Ψ(un) dx +
(Ω+y)∩{δ<|un|≤M }



�1−2∗/p       |wn| [p] dx + ε
Ω+y




    ≤ c(ε)



n    
|wn| [p] dx + ε
(Ω+y)∩{δ<|un|≤M }



Ψ(un) dx
(Ω+y)∩({|un|>M }∪{|un|≤δ})



|un| [2][∗∗] dx,
Ω+y




    - [�]
≤ c(ε)C



�� [�]
|wn| [2][∗] + |∇wn| [2][∗] dx
Ω+y



|un| [2][∗∗] dx
(Ω+y)∩({|un|>M }∪{|un|≤δ})



where C - 0 is a constant from the Sobolev inequality. Then we sum the inequalities over y ∈ Z [N] and get

- �� - [�] - �1−2∗/p 



       - [�]
R [N] [|][w][n][|][2][∗] [+][ |∇][w][n][|][2][∗] [dx]



sup
y∈Z [N]



R [N] [|][u][n][|][2][∗∗] [dx.]



��
R [N] [Ψ(][u][n][)][ dx][ ≤] [c][(][ε][)][C]







�1−2∗/p + ε



|wn(· + y)| [p] dx
Ω



Let us take (yn) ⊂ Z [N] such that


sup
y∈Z [N]




- 
|wn(· + y)| [p] dx ≤ 2
Ω



|wn(· + yn)| [p] dx
Ω


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 11



for any n ≥ 1. By the assumption un(· + yn) ⇀ 0 in D [2][,][2] (R [N] ) and passing to a subsequence we obtain
un(· + yn) → 0 in L [p] (Ω).
Since |wn(x)| ≤|un(x)|, we infer that wn(· + yn) → 0 in L [p] (Ω). Therefore











R [N] [|][u][n][|][2][∗∗] [dx,]



lim sup
n→∞



R [N] [Ψ(][u][n][)][ dx][ ≤] [ε][ lim sup] n→∞



and since ε > 0 is arbitrary, the assertion follows.
On the other hand, suppose that un(· + yn) does not converge to 0 in D [2][,][2] (R [N] ), for some (yn) in Z [N],
and Ψ(un) → 0 in L [1] (R [N] ). We may assume that un(· + yn) → u0 = 0 in L [p] (Ω) for some bounded domain
Ω ⊂ R [N] and 1 < p < 2 [∗∗] . Take any ε - 0, q - 2 [∗∗] and let us define Ψ(s) := min{|s| [p], ε [p][−][q] |s| [q] } for
s ∈ R. Then

      -      -      



          |un| [p] dx +
Ω+yn∩{|un|≥ε}




       ≥
R [N] [Ψ(][u][n][)][ dx]



n n   
|un| [p] dx +
Ω+yn



ε [q][−][p] |un| [q] dx
Ω+yn∩{|un|≤ε}




  =

  ≥



ε [p][−][q] |un| [q] −|un| [p] dx
Ω+yn∩{|un|≤ε}



|un| [p] dx − ε [p] |Ω|.
Ω+yn



Thus we get un(· + yn) → 0 in L [p] (Ω) and this contradicts u0 = 0. 

Proof of Lemma 4.1. Suppose that there is (yn) ⊂ Z [N] such that un(· + yn) does not converge weakly to 0
in D [2][,][2] (R [N] ). Since un(· + yn) is bounded, there is u0 = 0 such that, up to a subsequence,

un(· + yn) ⇀u0 in D [2][,][2] (R [N] ),

as n →∞. We find y ∈ R [N] such that u0χB(y,r) = 0 in L [2] (B(y, r)). Observe that, passing to a subsequence, we may assume that un(· + yn) → u0 in L [2] (B(y, r)). Then, in view of (4.1)

          -           



          |un(· + yn)| [2] dx =
B(y,r)



|un| [2] dx → 0
B(yn+y,r)



as n →∞, which contradicts the fact un(· + yn) → u0 = 0 in L [2] (B(y, r)). Therefore un(· + yn) ⇀ 0 in
D [2][,][2] (R [N] ) for any (yn) ⊂ Z [N] and by Lemma 4.2 we conclude. 

5. Proof of Theorem 1.3



In this section we adapt a variational approach from [20, Section 3] for the bi-Laplacian. Let



G−(s) :=



�� s
for s ≥ 0,
�00 [max][{−][g][(][t][)][,][ 0][}][ dt]
for s < 0.
s [max][{][g][(][t][)][,][ 0][}][ dt]



Notice that G+, G− ≥ 0 and G = G+ − G−.
First, we sketch our approach with an approximation Jε of J and present some auxiliary lemmas. The
proof of Theorem 1.3 is postponed to the end of the section. Let

g+(s) := G [′] + [(][s][)] and g−(s) := g+(s) − g(s), s ∈ R.

         - s
Notice that G−(s) = 0 [g][−][(][t][)][ dt][ ≥] [0][, for][ s][ ∈] [R][.] [In view of (g1) and (g3), there is some][ c >][ 0][ such that for]
every s ∈ R

(5.1) |G+(s)| ≤ c|s| [2][∗∗],

so G+(u) ∈ L [1] (R [N] ) whenever u ∈D [2][,][2] (R [N] ) ⊂ L [2][∗∗] (R [N] ). On the other hand, G−(u) may not be
integrable, for u ∈D [2][,][2] (R [N] ), unless G−(u) ≤ c|u| [2][∗∗] for some c - 0. To overcome this problem, for


12 J. MEDERSKI AND J. SIEMIANOWSKI



ε ∈ (0, 1), we define ϕε : R → [0, 1] by


ϕε(s) :=




1 for |s| ≤ ε,
ε [2][∗∗−][1] [|][s][|][2][∗∗][−][1]
1 for |s| ≥ ε.



We introduce a new functional




      
  - [(][u][)][ dx][ −]
R [N] [G][ε]



(5.2) Jε(u) := [1]







2




     R [N] [|][∆][u][|][2][ +]



R [N] [G][+][(][u][)][ dx,]




        - s
where G [ε] - [(][s][) :=] 0 [ϕ][ε][(][t][)][g][−][(][t][)][ dt][,][ s][ ∈] [R][.] [By (g0), there is][ c][(][ε][)][ >][ 0][ such that]



(5.3) |ϕε(s)g−(s)| ≤ c(ε)|s| [2][∗∗][−][1], s ∈ R.

This implies that G [ε] - [(][s][)][ ≤] [c][(][ε][)][|][s][|][2][∗∗] [for any][ s][ ∈] [R][ and some constant][ c][(][ε][)][ >][ 0][ depending on][ ε >][ 0][. Hence,]
for ε ∈ (0, 1), Jε is well-defined on D [2][,][2] (R [N] ), continuous and Jε [′] [(][u][)(][v][)][ exists for any][ u] [∈D][2][,][2][(][R][N] [)][ and]
v ∈C0 [∞][(][R][N] [)][.] [Therefore,] [we] [say] [that] [u] [is] [a] [critical] [point] [of] [J][ε] [provided] [that] [J] ε [′][(][u][)(][v][)] [=] [0] [for] [any]
v ∈C0 [∞][(][R][N] [)][.]
We define, for ε ∈ (0, 1),



Gε := G+ − G [ε] - [,]

    -    Mε := u ∈D [2][,][2] (R [N] ) \ {0} :




      R [N] [|][∆][u][|][2][ −] [2][∗∗]




      ,
R [N] [G][ε][(][u][)][ dx][ = 0]




   -    Pε := u ∈D [2][,][2] (R [N] ) :




      = ∅,
R [N] [G][ε][(][u][)][ dx >][ 0]



cε := inf
u∈Mε [J][ε][(][u][)][.]

and introduce the map mPε : Pε →Mε given by


mPε(u) = u(rε·),



where




    ∗∗ [�]
2
rε = rε(u) := 



2 [∗∗] [�]




      - 1
4
R [N] [G][ε][(][u][)][ dx]

.
∥u∥ [1][/][2]




      - 1
4
R [N] [G][ε][(][u][)][ dx]



R [N] [G][ε][(][u][)][ dx]




�1/4
=



R [N] [|][∆][u][|][2]



We check that mP�ε is well-defined. If u ∈Pε, then



ε
R [N] [|][∆(][m][P][ε][(][u][)(][x][)][|][2][ dx][ =][ r][4][−][N]








 -  = 2 [∗∗]


 -  = 2 [∗∗]


 -  = 2 [∗∗]



R [N] [|][∆][u][|][2][ dx]




    - [4][−][N]
4 N−4
∥u∥ 2
R [N] [G][ε][(][u][)][ dx]




    rε [−][N]
R [N] [G][ε][(][u][)][ dx]





2 ∥u∥ [2]




    - N
∥u∥ 2

       
R [N] [G][ε][(][u][)][ dx]

[∗∗] [�]



2

2 [∗∗] [�] [N] [G][ε][(]




      - N
4
R [N] [G][ε][(][u][)][ dx]




   = 2 [∗∗]



R [N] [G][ε][(][m][P][ε][(][u][)(][x][))][ dx.]







LEMMA 5.1. For every δ  - 0 there is cδ  - 0 such that

Gε(u + v) − Gε(u) − δ|u| [2][∗∗] ≤ cδ|v| [2][∗∗]


for all u, v ∈ R.


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 13


PROOF. First, we show that for every δ  - 0 there is c(δ) > 0 such that

(5.4) |G [ε] - [(][u][ +][ v][)][ −] [G][ε] - [(][u][)][| ≤] [δ][|][u][|][2][∗∗] [+][ c][(][δ][)][|][v][|][2][∗∗] [,] u, v ∈ R.


Fix δ - 0 and u, v ∈ R. By the mean value theorem, there is θ ∈ (0, 1) such that

|G [ε]          - [(][u][ +][ v][)][ −] [G][ε]          - [(][u][)][| ≤|][ϕ][ε][(][u][ +][ θv][)][g][−][(][u][ +][ θv][)][||][v][|]

≤ c(ε)|u + θv| [2][∗∗][−][1] |v|

≤ c1(ε)|u| [2][∗∗][−][1] |v| + c1(ε)|v| [2][∗∗],


where we used (5.3). We exploit the Young inequality with δ/c1(ε)

δ 2 [∗∗]
|u| [2][∗∗][−][1] |v| ≤ where p = [q] [= 2][∗∗][,]
c1(ε) [|][u][|][(2][∗∗][−][1)][p][ +][ c][2][(][δ, ε][)][|][v][|][q] [,] 2 [∗∗]              - 1 [,]


to obtain
|G [ε]            - [(][u][ +][ v][)][ −] [G][ε]            - [(][u][)][| ≤] [δ][|][u][|][2][∗∗] [+][ c][3][(][δ, ε][)][|][v][|][2][∗∗] [,]

what proves the assertion.
Now, we show that for every δ   - 0 there is c(δ)   - 0 such that

G+(u + v) − G+(u) − δ|u| [2][∗∗] ≤ c(δ)|v| [2][∗∗], u, v ∈ R.


Fix δ - 0 and u, v ∈ R. By (g1) and (g3), there are 0 < η < M such that


2
G+(s) ≤
2 [2][∗∗] [δ][|][s][|][2][∗∗] [,]

if |s| < η or |s| > M . We consider four cases.
Case I: |u + v| < η or |u + v| > M .
We use the fact that G+ ≥ 0 and obtain

                         2
G+(u + v) − G+(u) ≤ G+(u + v) ≤ |u| [2][∗∗] + |v| [2][∗∗] [�],
2 [2][∗∗] [δ][|][u][ +][ v][|][2][∗∗] [≤] [δ]

what proves the assertion.
Case II: η ≤|u + v| ≤ M and |v| > M .
There is c > 0 such that G+(s) ≤ c|s| [2][∗∗], for every s ∈ R, so

G+(u + v) − G+(u) ≤ G+(u + v) ≤ c|u + v| [2][∗∗] ≤ cM [2][∗∗] ≤ c|v| [2][∗∗]


and we are done.
Case III: η ≤|u + v| ≤ M and η/2 ≤|v| ≤ M .

      -      The set C := (u, v) ∈ R [2] | η ≤|u + v| ≤ M and η/2 ≤|v| ≤ M is compact and the function h :

C → R, given by h(u, v) := [G][+][(][u][+][v][)][−][G][+][(][u][)][−][δ][|][u][|][2][∗∗], is continuous. Thus, there is c(δ) - 0 such that

|v| [2][∗∗]
max(u,v)∈C h(u, v) ≤ c(δ) and we are done.
Case IV: η ≤|u + v| ≤ M and |v| < η/2.
By the continuity of g+ and by (g0), there is c(η) such that

|g+(s)| ≤ c(η)|s| [2][∗∗][−][1], |s| ≥ [η]

2 [.]

By the mean value theorem, there is θ ∈ (0, 1) such that


G+(u + v) − G+(u) = g+(u + θv)v.


Notice that |u + θv| ≥|u + v| − (1 − θ)|v| > η − η/2 = η/2, so combining the above we obtain

G+(u + v) − G+(u) ≤ c(η)|u + θv| [2][∗∗][−][1] |v|.


We then proceed as in the first part of the proof.


14 J. MEDERSKI AND J. SIEMIANOWSKI


Finally, we use the above results to deduce

                             -                             Gε(u + v) − Gε(u) = G+(u + v) − G+(u) − G [ε]        - [(][u][ +][ v][)][ −] [G][ε]        - [(][u][)]

≤ δ|u| [2][∗∗] + c(δ)|v| [2][∗∗] + |G [ε]           - [(][u][ +][ v][)][ −] [G][ε]           - [(][u][)][|]

               ≤ 2 δ|u| [2][∗∗] + c(δ)|v| [2][∗∗] [�] .


LEMMA 5.2. Suppose that (un) ⊂Mε, Jε(un) → cε and

un ⇀ u� ̸= 0 in D [2][,][2] (R [N] ), un(x) → u�(x) for a.e. x ∈ R [N]

for some �u ∈D [2][,][2] (R [N] ). Then un → u�, �u is a critical point of Jε and Jε(u�) = cε.


PROOF. It follows, by Lemma 5.1, that for every δ  - 0 theres is c(δ) > 0 such that

|Gε(u + v) − Gε(u)| ≤ δ|u| [2][∗∗] + c(δ)|v| [2][∗∗], u, v ∈ R.







Thus taking any v ∈C0 [∞][(][R][N] [)][ and][ t][ ∈] [R][ we observe that][ (][G][ε][(][u][n][ +][ tv][)][ −] [G][ε][(][u][n][))][ is uniformly integrable]
and tight. In view of Vitali’s convergence theorem we have








            R [N] [G][ε][(][u][n][ +][ tv][)][ −] [G][ε][(][u][n][)][ dx][ =]



lim
n→∞



R [N] [G][ε][(][u][�][ +][ tv][)][ −] [G][ε][(][u][�][)][ dx.]



Since each un ∈Mε, we get

cε ← Jε(un) = [1]

2



R [N] [G][ε][(][u][n][)][ dx,]




     2∗∗
R [N] [G][ε][(][u][n][)][ dx][ =] 2



��

∗∗

2 [−] [1]








      R [N] [|][∆][u][n][|][2][ dx][ −]



so


(5.5) A := lim
n→∞


Combining the above we have

      



       R [N] [G][ε][(][u][n][)][ dx][ +]



�−1
cε   - 0.








[1]
R [N] [G][ε][(][u][n][)][ dx][ =] 2



2 [∗∗]




1
2 [−] 2 [1][∗∗]








        R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]



R [N] [G][ε][(][u][�][)][ dx.]



lim
n→∞
(5.6)




[lim]
R [N] [G][ε][(][u][n][ +][ tv][)][ dx][ =] n→∞

          = A +



R R 
R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]



R [N] [G][ε][(][u][�][)][ dx]



By (5.5) and Lemma 5.1, un + tv ∈Pε for sufficiently large n and sufficiently small |t|. Thus and by (5.6),
for sufficiently small |t|, we have




     
    - [N][−][4]
N
R [N] [G][ε][(][u][n][)][ dx]



1
lim
n→∞ t



���




      - [N][−][4] ��
N

       R [N] [G][ε][(][u][n][ +][ tv][)][ dx]






.



= [1]

t



�� - A +

R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]




    - [N][−][4]
N N−4

     - A N
R [N] [G][ε][(][u][�][)][ dx]



and, consequently, by the Lebesgue dominated convergence theorem
(5.7)




        R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]








    - [N][−][4]
N N−4

     - A N
R [N] [G][ε][(][u][�][)][ dx]




 
4

N



1
lim
t→0 t



�� A +



R [N] [g][ε][(][u][�][)][v dx,]



N




[−] [4]
= [N]



−4
A N
N



where gε := G [′] ε [=][ g][+] [−] [ϕ][ε][g][−][.]
If un + tv ∈Pε, then Jε(mPε(un + tv)) ≥ cε, so




     1
rε(un + tv) [4][−][N]
2 [−] 2 [1]



��



2 [∗∗]



R [N] [|][∆(][u][n][ +][ tv][)][|][2][ dx][ ≥] [c][ε][.]


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 15


Raising both sides to the 4/N -power yields




    1
(5.8)
2 [−] 2 [1][∗∗]



R [N] [|][∆(][u][n][ +][ tv][)][|][2][ dx][ ≥] [c]




- [4]
N [�]



4
N
ε




- - - [N][−][4]

N

2 [∗∗] .

R [N] [G][ε][(][u][n][ +][ tv][)][ dx]



Assumptions un ∈Mε and Jε(un) → cε imply that




             (5.9)



R [N] [|][∆][u][n][|][2][ dx][ →] [c][ε]




1
2 [−] 2 [1][∗∗]



�−1
.



For all n and t, we have

    



    .
R [N] [|][∆][u][n][|][2][ dx]




[t]
R [N] [∆][u][n][∆][v dx][ +] 2







��



2




[1]
R [N] [|][∆][v][|][2][ dx][ =] 2t



2t




         -          
.

R [N] [|][∆(][u][n][ +][ tv][)][|][2][ dx][ −] R [N] [|][∆][u][n][|][2][ dx]



Hence, by (5.8) and since un ∈Mε, for t > 0,

- 



[t]
R [N] [∆][u][n][∆][v dx][ +] 2







R [N] [|][∆][v][|][2][ dx][ ≥]




      - [N][−][4]      -      N

       - 2 [∗∗]
R [N] [G][ε][(][u][n][ +][ tv][)][ dx]







2




    - [N][−][4] ��
N
R [N] [G][ε][(][u][n][)][ dx]




    - 4     N
R [N] [|][∆][u][n][|][2][ dx]



1
2t



4

cεN




1
2 [−] 2 [1]



2 [∗∗]




- [−][4] N [�]
2 [∗∗]



.



Letting n →∞, by (5.6), (5.5) and (5.9), we deduce that, for sufficiently small t > 0,

 - 



[t]
R [N] [∆][u][�][∆][v dx][ +] 2







2



R [N] [|][∆][v][|][2][ dx]



�� [N][−][4]
N N−4

      - (2 [∗∗] A) N
R [N] [G][ε][(][u][�][)][ dx]




- [−][4] �� - N
2 [∗∗] A +







≥ [1]



4
N
ε




1
2 [−] 2 [1]



2 [∗∗]



2t [c]




        R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]




    - [N][−][4]
N N−4

     - A N
R [N] [G][ε][(][u][�][)][ dx]






.



= [2][∗∗]



t



4
N [1]
2 [A] t



�� A +




        R [N] [G][ε][(][u][�][ +][ tv][)][ dx][ −]



N



We pass to the limit as t → 0 [+] and use (5.7) to get

        



      R [N] [g][ε][(][u][�][)][v dx][ =]



R [N] [∆][u][�][∆][v dx][ ≥] [2] 2 [∗∗]




[∗∗] N - 4

2 N







R [N] [g][ε][(][u][�][)][v dx.]



N



Since v ∈ C0 [∞][(][R][N] [)] [was] [arbitrary] [we] [infer] [that] [u][�] [is] [a] [critical] [point] [of] [J][ε][.] [We] [use] [the] [Pohožaev] [identity]
Theorem 1.2 to the equation ∆ [2] u = gε(u) with Gε ∈ L [1] (R [N] ), to deduce that �u ∈Mε, what leads to



��




    1
cε ≤ Jε(u�) =
2 [−] 2 [1]



��




1
2 [−] 2 [1]



2 [∗∗]



R [N] [|][∆][u][�][|][2][ dx][ ≤] [lim inf] n→∞



2 [∗∗]




[lim]
R [N] [|][∆][u][n][|][2][ dx][ =] n→∞ [J][ε][(][u][n][) =][ c][ε][,]



where the weak l.s.c of the norm was used. Thus, Jε(u�) = cε and ∥un∥→∥u�∥, so un → u� in D [2][,][2] (R [N] ).

                           


PROOF OF THEOREM 1.3. Take a minimizing sequence (un) in Mε of Jε, i.e., Jε(un) → cε. Since
un ∈Mε, n ≥ 1, we have




   1
Jε(un) =
2 [−] 2 [1]



��



2 [∗∗]



R [N] [|][∆][u][n][|][2][ dx][ →] [c][ε][,]



and so (un) is bounded in D [2][,][2] (R [N] ). Moreover, we have




cε.




       R [N] [G][+][(][u][n][)][ dx][ ≥]




  2 [∗∗]




     1
R [N] [|][∆][u][n][|][2][ dx][ →] 2 [−] 2 [1]



2 [∗∗]



By the assumption G+ satisfies (4.2), so (4.1) is not satisfied. Passing to a subsequence, we may choose
(yn) in R [N] and 0 ̸= uε ∈D [2][,][2] (R [N] ) such that

un(· + yn) ⇀uε in D [2][,][2] (R [N] ), un(x + yn) → uε(x) for a.e. x ∈ R [N],


16 J. MEDERSKI AND J. SIEMIANOWSKI



as n →∞. In view of Lemma 5.2, uε ∈Mε is a critical point of Jε at the level cε.
Choose εn → 0 [+] . Fix an arbitrary u ∈M. Since Gε(s) ≥ G(s), for all s ∈ R and ε ∈ (0, 1), we
deduce that - - 



       R [N] [G][ε][n][(][u][)][ dx][ ≥]




[1]
R [N] [G][(][u][)][ dx][ =] 2







2 [∗∗]



R [N] [|][∆][u][|][2][ dx >][ 0][,]



so mPεn (u) ∈Mεn is well-defined. We have



��
∗∗ [�]
2




         1
Jεn(uεn) ≤ Jεn(mPεn (u)) = 2 [−] 2 [1][∗∗]




- R �� rεn (u) [4][−][N]



R [N] [|][∆][u][|][2][ dx]





R [N] [|][∆][u][|][2][ dx]



R [N] [G][ε][n][(][u][)][ dx]





- [4][−][N]
4



�− [N] 4 [−][4]
R [N] [G][ε][n][(][u][)][ dx]




 1
=
2 [−] 2 [1][∗∗]



���



�− [N] 4 [−][4]
R [N] [G][(][u][)][ dx]




 1
≤
2 [−] 2 [1][∗∗]



���




    - N    4 [�]
2 [∗∗]
R [N] [|][∆][u][|][2][ dx]

    - [N]    4 [�]
2 [∗∗]
R [N] [|][∆][u][|][2][ dx]




- �� 



 1
=
2 [−] 2 [1][∗∗]



��

R [N] [|][∆][u][|][2][ dx][ =][ J][(][u][)][.]



��



=(�




     - [N][−][4]

4

R [N] [|][∆][u][|][2][ dx][)]



Thus Jεn(uεn) ≤ inf M J and




         
(5.10)




     1
R [N] [|][∆][u][ε][n][|][2][ dx][ ≤] 2 [−] 2 [1]



2 [∗∗]



�−1
inf for every n.
M [J,]



We have Gε(s) ≤ G1/2(s), for all s ∈ R and ε ∈ (0, 1/2), so

     -     -     



       R [N] [G][1][/][2][(][u][ε][)][ dx][ ≥]



1
R [N] [G][ε][(][u][ε][)][ dx][ =] 2 [∗∗]








[=][⇒] [u][ε] [∈P][1][/][2][,]
R [N] [|][∆][u][ε][|][2][ dx >][ 0]



and some calculations yield



Jε(uε) ≥ J1/2(mP1/2 (uε)) ≥ J1/2(u1/2).



Therefore, we get




     1
R [N] [|][∆][u][ε][n][|][2][ dx][ =] 2 [−] 2 [1]



�−1
J1/2(u1/2) > 0.




  2 [∗∗]




       R [N] [G][+][(][u][ε][n][)][ dx][ ≥]



�−1 1
Jεn(uεn) ≥ 2 [−] 2 [1][∗∗]



�−1 1
Jεn(uεn) ≥ 2 [−] 2 [1]




                    By (5.10), (uεn) is bounded in D [2][,][2] (R [N] ) and



2 [∗∗]



By (5.10), (uεn) is bounded in D (R ) and R [N] [G][+][(][u][ε][n][)][ dx] [>] [c] [>] [0][,] [for] [some] [constant] [c][.] [In] [view] [of]

Lemma 4.1, (4.1) is not satisfied. Passing to a subsequence, there is (yn) in R [N] such that uεn(· + yn) ⇀
u0 = 0 and uεn(x + yn) → u0(x) a.e. in R [N] . We write �un := uεn(· + yn) for short. Since g− is continuous
and g−(0) = 0, one may check that, for every v ∈ C0 [∞][(][R][N] [)][,]
���� 1 |u�n| [2][∗∗][−][1] χ{|un|≤εn}g−(u�n)v���� ≤ ��χ{|un|≤εn}g−(u�n)v�� → 0 a.e. in R [N]
εn [2][∗∗][−][1]       -       
and ��χ{|u�n|>ε� n}g−(u�n)v − g−(u0)v�� → 0 a.e. in R [N] .

Due to the estimate |g−(u�n)v| ≤ c 1 + |u�n| [2][∗∗][−][1][�] |v|, the family {g−(u�n)v} is uniformly integrable (and
tight because of the compact support). In view of Vitali’s convergence theorem

 


and ��χ{|u�n|>ε� n}g−(u�n)v − g−(u0)v�� → 0 a.e. in R [N] .

[∗∗] [�]




[dx]
R [N] [|][ϕ][ε][n][(][u][�][n][)][g][−][(][u][�][n][)][v][ −] [g][−][(][u][0][)][v][|]




 ≤



R [N]




                1
���� |u�n| [2][∗∗][−][1] χ{|un|≤εn}g−(u�n)v���� dx +
ε [2] n [∗∗][−][1] 


R [N]



��χ{|u�n|>εn}g−(u�n)v − g−(u0)v�� dx → 0,


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 17



as n →∞. Similarly, we obtain

             



       R [N] [g][+][(][u][�][n][)][v dx][ →] R [N] [g][+][(][u][0][)][v dx.]




       R [N] [g][+][(][u][�][n][)][v dx][ →]



Gathering the above we deduce that




       R [N] [g][+][(][u][�][n][)][v dx][ +]

       R [N] [g][+][(][u][0][)][v dx][ +]




       R [N] [∆][u][�][n][∆][v dx][ −]




      Jε [′] n [(][u][�][n][)(][v][) =]




       R [N] [∆][u][0][∆][v dx][ −]



R [N] [ϕ][ε][n][(][u][�][n][)][g][−][(][u][�][n][)][v dx]




 →



R [N] [g][−][(][u][0][)][v dx.]



Each �un is a critical point of Jεn, since so is uεn (translation invariance), hence

             -              



       R [N] [∆][u][0][∆][v dx][ =]



R [N] [g][(][u][0][)][v dx,]



i.e., u0 is a weak solution to (1.1). By Lebesgue’s dominated convergence theorem one may show that

G [ε]          - [n][(][u][�][n][)][ →] [G][−][(][u][0][)] a.e. in R [N],



as n →∞, and, on the other hand,




< ∞,




  2 [∗∗]




        
  - [(][u][�][n][)][ dx][ = 2][∗∗]
R [N] [G][ε][n]




       R [N] [G][+][(][u][�][n][)][ dx][ −]




     sup ∥u�n∥D2,2(RN )
R [N] [|][∆][u][�][n][|][2][ dx][ ≤] [c] n≥1



where we used the fact that �un ∈Mεn, (5.1) and (5.10). By Fatou’s lemma and by the above

           -           


R [N] [G][−][(][u][0][)][ dx][ ≤] [lim inf] n→∞




  - [(][u][�][n][)][ dx <][ ∞][,]
R [N] [G][ε][n]



namely, we have shown that G−(u0) ∈ L [1] (R [N] ). By the Pohožaev identity, we infer that u0 ∈M. Lastly,
we show that J(u0) = infM J. We use the weak l.s.c. of the norm and (5.10) to find that




   1
J(u0) =
2 [−] 2 [1]



��



R [N] [|][∆][u][0][|][2][ dx][ ≤] [lim inf] n→∞



R [N] [|][∆][u][�][n][|][2][ dx]




1
2 [−] 2 [1]



��



2 [∗∗]



��



2 [∗∗]



= lim inf
n→∞




1
2 [−] 2 [1]



2 [∗∗]



R [N] [|][∆][u][ε][n][|][2][ dx][ ≤] [inf] M [J.]







6. Biharmonic logarithmic inequality




               LEMMA 6.1. If u ∈D [2][,][2] (R [N] ) and



) and R [N] [|][u][|][2][ dx][ = 1][, then]

- ��



��
R [N] [|∇][u][|][2][ dx <]



�1/2
.
R [N] [|][∆][u][|][2][ dx]



PROOF. We rely on ideas from [4]. Let us define the Fourier transform u� of u (whenever possible) as







ξ ∈ R [N] .
R [N] [e][−][ix][·][ξ][u][(][x][)][ dx,]




          If u ∈D [2][,][2] (R [N] ) and



1
u�(ξ) =

(2π) [N/][2]



R [N] [|][u][|][2][ dx][ = 1][, then][ u][ ∈] [H] [2][(][R][N] [)][ and by the Plancharel theorem]


∥u∥L2(RN ) = ∥u�∥L2(RN ),

∥∇u∥L2(RN ) = ∥∇ [�] u∥L2(RN ) = ∥ξu�∥L2(RN ),

∥∆u∥L2(RN ) = ∥∆ [�] u∥L2(RN ) = ∥|ξ| [2] u�∥L2(RN ).


18 J. MEDERSKI AND J. SIEMIANOWSKI



By the Cauchy–Schwartz inequality we get
��      


�1/4 ��
R [N] [||][ξ][|][2][u][�][(][ξ][)][|][2][ dξ]



�1/2 ��
≤
R [N] [|][ξ][u][�][(][ξ][)][|][2][ dξ]



�1/4
.
R [N] [|][u][�][(][ξ][)][|][2][ dξ]



and the assertion follows with the non-strict inequality. Recall that the equality in the Cauchy–Schwartz
inequality holds if and only if |ξ| [2] u�(ξ) = λu�(ξ) for some λ, what implies u� = 0. Hence the inequality in
the statement is in fact strict. 


Proof of Theorem 1.4. Observe that the following inequality holds




     - [�]
(6.1)



for any u ∈D [2][,][2] (R [N] ),
R [N] [|][u][|][2][ log][ |][u][|][ dx,]




    - N
N−4 ≥ CN,log
R [N] [|][∆][u][|][2][ dx]







where



CN,log = 2 [∗∗][�] [1]



2 [∗∗]




[1]

2 [−] 2 [1]



�− N4−4 N4−4
(inf .
M [J][)]




                         Indeed, it is enough to consider u ∈D [2][,][2] (R [N] ) such that



Indeed, it is enough to consider u ∈D [2][,][2] (R [N] ) such that R [N] [|][u][|][2][ log][ |][u][|][ dx] [>] [0][.] [We then] [obtain] [u][(][r][·][)] [∈]

M, where




  ∗∗ [�]
2
r :=



R [N] [|][u][|][2][ log][ |][u][|][ dx]

 
R [N] [|][∆][u][|][2]



R [N] [|][u][|][2][ log][ |][u][|][ dx]

 


�1/4
.



Hence J(u(r·)) ≥ infM J and we get (6.1).
Now note that (6.1) is equivalent to




   - [�]
(6.2)




     - N
R [N] [|][∆][u][|][2][ dx] N−4 ≥ CN,log maxα∈R




- e [−][α][2][∗∗] [�], for u ∈D [2][,][2] (R [N] ).

R [N] [|][e][α][u][|][2][ log][ |][e][α][u][|][ dx]




       Assuming that



R [N] [|][u][|][2][ dx] [=] [1][,] [the] [maximum] [of] [the] [right] [hand] [side] [of] [(][6.2][)] [is] [attained] [at] [α] [=] [N] 8 [−][4]



Assuming� that R [N] [|][u][|][2] [=] [1][,] [the] [maximum] [of] [the] [right] [hand] [side] [of] [(][6.2][)] [is] [attained] [at] [α] [=] 8 


R [N] [|][u][|][2][ log][ |][u][|][ dx][.] [Hence we get]




    - [�]
N
N - 4 [log]




    -     N              - 4
≥ log(CN,log) − α2 [∗∗] + 2α + log
R [N] [|][∆][u][|][2][ dx] 8







that is

       - [�]
N
N   - 4 [log]




    -     N        - 4 8
≥ log CN,log e [−][1][�] +
R [N] [|][∆][u][|][2][ dx] 8 N - 4



R [N] [|][u][|][2][ log][ |][u][|][ dx]







and
N




    
[−] [4]
≥ [N]
R [N] [|][∆][u][|][2][ dx] 8




  - [�]
8 [log]




   
[−] [4] N - 4

log CN,log
8 8




     
- 4

e [−][1][�] +
8



R [N] [|][u][|][2][ log][ |][u][|][ dx]



thus (1.7) holds.
We show that the constant in (1.7) is optimal, i.e., there is u ∈D [2][,][2] (R [N] ) such that the equality holds.
First of all, notice that if u0 is a minimizer given by Theorem 1.3, then for u0 we have the equality in (6.1):



��         - N

N−4

(6.3) = CN,log

R [N] [|][∆][u][0][|][2][ dx]





R [N] [|][u][0][|][2][ log][ |][u][0][|][ dx.]



e [α]
We use (6.1) for the family of functions ∥u0∥L2 [u][0] [∈D][2][,][2][(][R][N] [)][,][ α][ ∈] [R][, to get]




    - N    N−4
≥ CN,log∥u0∥L [2][∗∗][2] [−][2] e [(2][−][2][∗∗][)][α]
R [N] [|][∆][u][0][|][2][ dx]



∥u0∥L2 [u][0]



��

(6.4)



e [α]
����
R [N] [|][u][0][|][2][ log] ∥u0∥



dx, α ∈ R.
����



Now let us consider the function f : R → R given by




    - N
N−4
R [N] [|][∆][u][0][|][2][ dx]




             
e [α]

f (α) := CN,log∥u0∥L [2][∗∗][2] [−][2] e [(2][−][2][∗∗][)][α] R [N] [|][u][0][|][2][ log] ���� ∥u0∥L2 [u][0]



��
dx −
����


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 19



Note that




            
[−] [4]
f [′] (α) = 0 ⇐⇒ α = [N] 
8



2
u0
log

���� ����

∥u0∥L2



dx.
����



R [N]



u0
����
∥u0∥L2



����



On the other hand, f attains maximum at α = log(∥u0∥L2) in view of (6.4) and (6.3), thus

         


2
u0
log
����
∥u0∥L2



N   - 4
���� dx = - log(∥u0∥L2)
8



R [N]



u0
����
∥u0∥L2



����



or, equivalently,
1
∥u0∥ [2] L [2]








[N]
R [N] [|][∆][u][0][|][2][ dx][ =] 4



4 [,]



where we used the fact that u0 ∈M. Therefore we obtain the equality in (1.7) for the function ∥uu0∥0L2 [.]
Let us now suppose that




 =







R [N] [|][u][|][2][ log][ |][u][|][ dx]



N

8 [log]



N



��
8e
CN,log(N   - 4)



�(N −4)/N 
R [N] [|][∆][u][|][2][ dx]



�(N −4)/N 


for some u ∈D [2][,][2] (R [N] ) such that ∥u∥L2(RN ) = 1. Then




    - N
N−4 −α2 [∗∗] [�]
= CN,loge
R [N] [|][∆][u][|][2][ dx]




- [�]



R [N] [|][e][α][u][|][2][ log][ |][e][α][u][|][ dx]




   
[−][4] 
8



for α = [N] 8 [−][4] - R [N] [|][u][|][2][ log][ |][u][|][ dx][ and the equality] [in (][6.1][) holds for][ u][1] [:=] [e][α][u][.] [Hence][ J][(][u][0][)] [=] [inf] [M][ J]

for



for α = [N] [−][4]




          ∗∗ [�]
2
u0 := u1(r·) ∈M, where r =



R [N] [|][∆][u][1][|][2][ dx]



R [N] [|][u][1][|][2][ log][ |][u][1][|][ dx]




�1/4
.



Let us sketch the proof that u0 is a critical point of J. Firstly, note that, for every v ∈ C0 [∞][(][R][N] [)][,][ G][(][u][0] [+][v][)][ ∈]
L [1] (R [N] ), for G(s) := s [2] log |s|. Fix an arbitrary v ∈ C0 [∞][(][R][N] [)][.] [We use the fact] [that][ G][ is][ C] [1][-smooth] [and]
the Lebesgue dominated convergence theorem to get




    -    =
R [N] [G][(][u][0][)][ dx]



1
lim
t→0 t



�� 
R [N] [G][(][u][0][ +][ tv][)][ dx][ −]



��



R [N] [g][(][u][0][)][v dx.]




        By the continuity,



R [N] [G][(][u][0][ +][ tv][)][ dx >][ 0][, for sufficiently small][ |][t][|][ >][ 0][, so][ (][u][0][ +][ tv][)(][r][·][)][ ∈M][, where]




 ∗∗ [�]
2
r = 


2 R [N] [G][(][u][0][ +][ tv][)][ dx]




R [N] [|][∆(][u][0][ +][ tv][)][|][2][ dx]



�1/4
.



Hence
J((u0 + tv)(r·)) ≥ inf [=][ J][(][u][0][)]
M [J]



or, equivalently,

   1
2 [−] 2 [1][∗∗]




          -          2 [∗∗]
R [N] [|][∆(][u][0][ +][ tv][)][|][2][ dx][ ≥] [J][(][u][0][)][4][/N]



�4/N �



�(N −4)/N
.
R [N] [G][(][u][0][ +][ tv][)][ dx]



We then proceed similarly as in the last part of the proof of Lemma 5.2 to conclude that

             -              



       R [N] [∆][u][0][∆][v dx][ ≥]



R [N] [g][(][u][0][)][v dx,]



which yields that u0 is a critical point of J.


20 J. MEDERSKI AND J. SIEMIANOWSKI



Finally, we show the estimate of the constant� CN,log from Theorem 1.7. Observe that if u ∈D [2][,][2] (R [N] )
and [N] [|][u][|][2][ dx] [=] [1][,] [then] [u] [∈] [H] [2][(][R][N] [)][.] [In] [view] [of] [Lemma] [6.1] [and] [the] [logarithmic] [Sobolev] [inequality]



and R [N] [|][u][|][2][ dx] [=] [1][,] [then] [u] [∈] [H] [2][(][R][N] [)][.] [In] [view] [of] [Lemma] [6.1] [and] [the] [logarithmic] [Sobolev] [inequality]

(1.8) we obtain

         
  - ��  - [�] �� [�]  



    ,
R [N] [|][∆][u][|][2][ dx]



�1/2 [�]
R [N] [|][∆][u][|][2][ dx]



= [N]



��
2
8 [log] πeN




[N]
R [N] [|][u][|][2][ log(][|][u][|][)][ dx <] 4



��



�2 [�]



4 [log]




2
πeN



and so

         8e
CN,log(N               - 4)



�(N −4)/N 2
<
πeN



�2
.




                           

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

[10] M. del Pino and J. Dolbeault, The optimal Euclidean L [p] -Sobolev logarithmic inequality, J. Funct. Anal. 197 (2003), no. 1,
151–161.

[11] G. Fibich, B. Ilan, and G. Papanicolaou, Self-focusing with fourth-order dispersion, SIAM J. Appl. Math. 62 (2002), no. 4,
1437–1462.

[12] F. Gazzola, H.-C. Grunau, and G. Sweers, Polyharmonic boundary value problems, Lecture Notes in Mathematics, vol. 1991,
Springer-Verlag, Berlin, 2010. Positivity preserving and nonlinear higher order elliptic equations in bounded domains.

[13] L. Gross, Logarithmic Sobolev inequalities, Amer. J. Math. 97 (1975), no. 4, 1061–1083.

[14] E. H. Lieb and M. Loss, Analysis, 2nd ed., Graduate Studies in Mathematics, vol. 14, American Mathematical Society, Providence, RI, 2001.

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


BIHARMONIC NONLINEAR SCALAR FIELD EQUATIONS 21


[21] V. V. Meleshko, Selected topics in the history of the two-dimensional biharmonic problem, Appl. Mech. Rev. 56 (2003), 33-85.

[22] L. Nirenberg, Estimates and existence of solutions of elliptic equations, Comm. Pure Appl. Math. 9 (1956), 509–529.

[23] P. Pucci and J. Serrin, A general variational identity, Indiana Univ. Math. J. 35 (1986), no. 3, 681–703.

[24] A. P. S. Selvadurai, Partial differential equations in mechanics. 2, Springer-Verlag, Berlin, 2000. The biharmonic equation,
Poisson’s equation.

[25] R. C. A. M. Van der Vorst, Best constant for the embedding of the space H [2] ∩ H0 [1][(Ω)] [into] [L][2][N/][(][N][−][4)][(Ω)][,] [Differential]
Integral Equations 6 (1993), no. 2, 259–276.

[26] F. B. Weissler, Logarithmic Sobolev inequalities for the heat-diffusion semigroup, Trans. Am. Math. Soc. 237 (1978), 255–
269.


(J. Mederski)
INSTITUTE OF MATHEMATICS,
POLISH ACADEMY OF SCIENCES,

UL. S [´] NIADECKICH 8, 00-656 WARSAW, POLAND


AND
DEPARTMENT OF MATHEMATICS,
KARLSRUHE INSTITUTE OF TECHNOLOGY (KIT),
D-76128 KARLSRUHE, GERMANY
Email address: [jmederski@impan.pl](mailto:jmederski@impan.pl)


(J. Siemianowski)
FACULTY OF MATHEMATICS AND COMPUTER SCIENCES,
NICOLAUS COPERNICUS UNIVERSITY IN TORU N [´]

UL. GAGARINA 11, 87-100 TORU N [´], POLAND


AND
INSTITUTE OF MATHEMATICS,
POLISH ACADEMY OF SCIENCES,

UL. S [´] NIADECKICH 8, 00-656 WARSAW, POLAND


Email address: [jsiem@mat.umk.pl](mailto:jsiem@mat.umk.pl)


