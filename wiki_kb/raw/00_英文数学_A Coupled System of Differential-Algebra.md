---
title: "A Coupled System of Differential-Algebraic Equation and Hyperbolic Partial Differential Equation"
source_file: "A Coupled System of Differential-Algebraic Equation and Hyperbolic Partial Differential Equation.pdf"
source_url: ""
lang: "英文数学"
converter: markitdown
---

#### A Coupled System of Differential-Algebraic Equation and
#### Hyperbolic Partial Differential Equation Analysis and Optimal Control
#### Dennis Groh
#### Dennis Groh
## A Coupled System of Differential-Algebraic Equation and
## Hyperbolic Partial Differential Equation
#### Analysis and Optimal Control
##### Logos Verlag Berlin
λογος
Die Veröffentlichung wurde gefördert aus dem Open-Access-Publikationsfonds derHumboldt-Universität zu Berlin.
Hergestellt als Logos-Ökobuch.[https://www.logos-verlag.de/oekobuch](https://www.logos-verlag.de/oekobuch)
Logos Verlag Berlin GmbHGeorg-Knorr-Str. 4, Geb. 10, 12681 Berlin
##### You have to spend some energy and
##### <u>eort to see the beauty of math.</u>
##### (Maryam Mirzakhani)
#### Zusammenfassung
Diese Dissertation befasst sich mit der Analyse eines gekoppelten Systems der Form { (E u) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t),
′′ (1.1) v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t).
Es besteht aus einer semilinearen abstrakten dierential-algebraischen Gleichung (DAE) und einer semilinearen hyperbolischen partiellen Dierentialgleichung zwei- ter Ordnung. Beide Gleichungen sind durch die nichtlinearen Kopplungsoperatoren φ₁ und φ₂ miteinander gekoppelt.
Gekoppelte Systeme dieser Art können als spezielle abstrakte DAEs und als Verall- gemeinerungen von partiell dierential-algebraischen Gleichungen aufgefasst werden. Sie spielen in vielen Anwendungen wie der Modellierung von multiphysikalischen Systemen, bei der Simulation von Schaltkreisen, oder der Optimalsteuerung von Gasnetzwerken eine Rolle.
In der vorliegenden Arbeit diskutieren wir zunächst nur die abstrakte DAE und führen sogenannte Matrix-induzierte lineare Operatoren ein. Wir übertragen unter Nutzung dieser Operatoren einen Entkopplungsansatz für DAEs auf den unendlich- dimensionalen Fall der vorliegenden abstrakten DAE. In Kombination mit einer neu- artigen Index-1-Charakterisierung für semilineare abstrakte DAEs gelingt es uns, die inhärente gewöhnliche Dierentialgleichung und die algebraischen Nebenbedingun- gen aus der abstrakten DAE zu extrahieren und Existenz und Eindeutigkeit von Lösungen zu zeigen.
Anschließend verbinden wir die entwickelten Ansätze zur Behandlung von derartigen abstrakten DAEs mit bereits bekannten Ansätzen für die Analyse von hyperbolischen Gleichungen zweiter Ordnung, und schaen einen einheitlichen Rahmen, in dem wir das gekoppelte System (1.1) diskutieren können. Mithilfe eines Fixpunktansatzes zeigen wir Existenz und Eindeutigkeit von lokalen und globalen Lösungen zu diesem gekoppelten System.
Zu guter Letzt formulieren wir ein Optimalsteuerungsproblem, in dem das Sys- tem (1.1) als Nebenbedingung auftritt. Wir zeigen die Existenz einer optimalen globalen Steuerung und einer globalen Minimalstelle.
vii
#### Abstract
In this thesis, we analyze a coupled system of the form { (E u) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t),
′′ (1.1) v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t).
It consists of a semilinear abstract dierential-algebraic equation (DAE) and a semi- linear second order hyperbolic partial dierential equation. Both equations are cou- pled through the nonlinear coupling functions φ₁ and φ₂.
Coupled systems of the form (1.1) can be interpreted as a specic kind of abstract DAE or as a generalization to partial dierential-algebraic equations. They are rele- vant for a variety of applications, for instance the modeling of multiphysics systems, the simulation of circuits, or the optimal control of gas ow through a pipe network.
In this thesis, we rst discuss only the semilinear abstract DAE, and introduce so-called matrix-induced linear operators. Using these operators, we transfer a de- coupling strategy developed for DAEs to the innite-dimensional setting of abstract DAEs. In combination with a novel index-1 characterization for semilinear abstract DAEs, this allows to extract from the abstract DAE the inherent ordinary dieren- tial equation and the complementing algebraic equations. We then prove existence and uniqueness of solutions.
We combine the developed analytical techniques for semilinear abstract DAEs with matrix-induced linear operators with analytical tools known from the theory of sec- ond order hyperbolic equations to provide a framework suitable for the analysis of system (1.1). By means of a xed-point approach, we show existence and uniqueness of local and global solutions.
Finally, we formulate an optimal control problem where system (1.1) acts as a side condition. We show the existence of an optimal control and a global minimizer.
ix
#### Acknowledgements
First of all, I would like to thank my supervisor Prof. Dr. Caren Tischendorf. I could not have written this thesis if not for her kind oer to accept me into her working group. I would also like to thank the Berlin Mathematical School as well as the DFG funded Collaborative Research Center TRR 154. I was allowed to be associated to both and beneted from their networking activities and programs.
I wish to say thanks to Prof. Dr. Barbara Zwicknagl, my mentor within the Berlin Mathematical School. Her professional advice and her kindness helped more than once to push through dicult moments. I also wish to thank Prof. Dr. Axel Kröner for his support and motivating words. Gratitude is equally owed to Prof. Dr. Eti- enne Emmrich who acted as reviewer for this thesis.
I would also like to thank some of the most important sta members for technology, service, and administration at the Faculty of Mathematics and Natural Sciences as well as the Department of Mathematics of the Humboldt-Universität zu Berlin. I would like to thank Julia Brandt, Anne Dorow, Martin Gödeker, Carys Lewis, André Musch, Heike Pahlisch, and Gerlinde Schulz for their support and their tremendous work behind the scenes.
To my colleagues within and outside of our group, especially Dr. Jonas Pade, Henning Sauter, Dr. Maximilian Schade, Lukas Baumgärtner, Franz Bethke, and Prof. Dr. Daniel Walter, I am much obliged. With all of them, I have shared many fruitful discussions, thoughts, ideas, lunch breaks, and the occasional moment of frus- tration. I am also very grateful for my friends and fellow mathematicians Dr. Jen- nifer Rasch, Dr. Jo Andrea Brüggemann, and Dr. Caroline Löbhard, who went down that PhD road before me. Their strengths and determination has always been in- spiring.
Last but not least, I want to thank my family and my closest friends. I am thankful for the constant support, the encouragement, and the love I received from my parents and parents-in-law, my grandparents, my dear brother, and my sister-in-law. I want to thank Tina, Ronald, and Stephan, for their friendship, their trust, and all the things they have been teaching me for these last fteen years since our rst encounter. But most importantly, I want to thank Johanna and Janosch, for always being there for me, standing by, well, almost every decision I make, for their tenderness, their candor, for being a wellspring of light and joy. Thank you from the bottom of my heart.
xi
#### Contents
**1 Introduction 1**
**2 Analysis of an Abstract Semilinear DAE 5**
2.1 Matrix-induced Linear Operators.. .................. 9
2.2 Solution Spaces for Semilinear Abstract DAEs. ............ 13
2.3 Dissection-based Decoupling Procedure. ................ 19
2.4 Existence Theory. ............................ 26
2.5 Summary and Discussion. ....................... 36
**3 A Brief Introduction to Linear Wave Equations 41**
3.1 Linear Hyperbolic Partial Dierential Equations of Second Order.. 43
3.2 Linear Wave Equations. ........................ 47
3.3 Sample Applications..... ...................... 50
3.4 Summary. ................................ 52
**4 Analysis of a Coupled System 53**
4.1 Solution Spaces for the Coupled System.... ............ 55
4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave
Equation. ................................ 58
4.3 Analysis of a Coupled System of Abstract DAE and Semilinear Wave
Equation. ................................ 75
4.4 Summary and Discussion. ....................... 81
**5 A First Small Step Towards Optimal Control 85**
5.1 Problem Formulation ..... ...................... 86
5.2 Existence of a Global Minimizer.. .................. 88
5.3 Summary and Discussion. ....................... 91
**6 Conclusion and Outlook 93**
**Appendix 95**
**AGeneralized Inverses, Projections and Factorizations of Matrices 97**
**BTools from Functional Analysis 103**
B.1 Facts from Functional Analysis... .................. 104
xiii
<u>Contents</u>
B.2 On Sobolev Spaces.. .......................... 106
B.3 On Bochner Spaces .. .......................... 108
##### COn Abstract Dierential Equations and Operator Equations 117
C.1 Tools from Abstract ODE Theory.... ............... 117
C.2 Nemytskii Operators on Bochner Spaces. ............... 119
C.3 On Monotone Operators. ........................ 120
##### Bibliography 123
xiv
#### List of Assumptions
Assumption 1 (Time and Space). ...................... 4
Assumption 2 (E is singular).. ....................... 15
Assumption 3 (DAE (2.19) has a Properly Stated Leading Term)... .. 20
|Assumption 3 (DAE (2.19) has a Properly Stated Leading Term)||||....|. 20|
|---|---|---|---|---|---|
|Assumption 4 (Index-1 Characterization of DAE (2.19))|||....|.....|. 29|
|Assumption 5 (for Existence and Uniqueness of a Solution to DAE (2.19))|||||31|
|Assumption 6 (Framework for Abstract Hyperbolic PDE of Second Order)|||||43|
|Assumption 7 (Framework for Coupled System (4.1))..|||...|......|. 57|
|Assumption 8 (for Existence and Uniqueness of a Solution to System (4.1))|||||68|
|Assumption 9 (Framework for Coupled System (4.35))|||.....|.....|. 76|
|Assumption 10 (Index-1 Characterization for Coupled System (4.35))..|||||. 78|
|Assumption 11 (Framework for the Optimal Control Problem (5.2))||||..|. 87|
xv
#### 1 Introduction
Many natural phenomena are modeled by dierential equations, whether it is to describe the interaction between physical particles, or to understand how chemical substances react and diuse, whether it is to model the spreading of a new virus, or to predict the climate change or local weather. The ever-increasing computational power and the availability of larger and larger sets of data allow to describe all of these phenomena using better suited and more complex sets of dierential equations in which the describing components of the underlying physical, chemical, or biological system are intimately coupled. Understanding these systems and knowing how to inuence them in a desirable way helps to develop new strategies, e. g. for how to practice agriculture in a more sustainable and cost ecient way, it helps to predict consequences of events like earthquakes, hurricanes, and inundation, and it indicates how to counteract for instance undesirable eects of long-term medication.
With this thesis we try to help towards a better understanding of coupled systems of dierent kinds of dierential equations. More specically, we analyze a coupled system of an abstract dierential-algebraic equation (DAE) and a specic second- order hyperbolic partial dierential equation (PDE), the wave equation. It takes the form { (E u) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t), (1.1a)
v ′′
(t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t). (1.1b)
This coupled system consists of the semilinear abstract DAE (1.1a) and the semilin- ear wave equation (1.1b). The two solution variables u and v are both functions of the time t and of spatial variables not explicitly stated here. The linear operator E of (1.1a) is a so-called matrix-induced linear operator introduced in Chapter 2, and the coupling functions φ₁ and φ₂ are nonlinear but continuous. The system can be manipulated through right-hand side functions q₁ and q₂. For the analysis in this thesis, it will be complemented by appropriate initial and boundary conditions.
The main goal of this thesis is the analysis of the system (1.1). In particular, we want to provide a framework in which existence and uniqueness of local and global solutions can be ensured. The perhaps most challenging task in this analysis is to nd a common setting in which all components of the coupled systems can be discussed satisfactorily. In the course of mathematical research history, the analytical techniques and tools developed to analyze a specic dierential equation became more and more tailored and bespoke. Our intent is, in a sense, to go a step in the opposite direction, to see if it is possible to consolidate the dierent settings for
##### <u>1 Introduction</u>
abstract DAEs and hyperbolic second order PDEs, and to strive towards a more unied framework which is equally suited for both. Thus, we are driven not only by an external but also an inner-mathematical motivation.
##### Main Contributions
We want to emphasize the main contributions of this thesis. First, we develop the notion of so-called *matrix-induced linear operators*. Although these kinds of oper- ators appear frequently but implicitly in the research literature on abstract DAEs,
e. g. [86, 128], and although they promise to be very useful, particularly for the analysis of coupled systems, they have not been discussed in the context of abstract DAEs so far. Using this kind of operators, we are able to translate a decoupling approach that was developed for DAEs in [64] to the innite-dimensional framework of abstract DAEs. In combination with a novel theoretical existence result for a cer- tain type of operator equation, see Theorem 2.20, this decoupling approach allows to prove existence and uniqueness of strong solutions for a semilinear abstract DAE of the form (1.1a). Second, we provide a framework for the coupled system (1.1). To this end, we rst discuss a related system where the wave equation (1.1b) is coupled with an abstract ordinary dierential equation (ODE) instead of (1.1a). We prove existence and uniqueness of local as well as global solutions to this related coupled system by means of a xed-point approach. Afterwards, we use the techniques developed in Chapter 2 to transfer the results to system (1.1). Third, we take a glance at an optimal control problem which is constrained by the related coupled system of abstract ODE and wave equation. We discuss whether the framework previously chosen for the analysis of (1.1) is equally appropriate for the optimal control problem, and we show under strong assumptions that the optimal control problem admits a global minimizer.
##### Structure and Literature
Observe that each chapter is more or less similarly structured. Due to the inherent consolidating character of this thesis, each chapter starts with a detailed introduction into the chapter’s general topic. We then give an overview of the contributions of the chapter and integrate our results into existing research literature. Therefore, we will keep this overview short.

# Chapter 2 is dedicated to our rst main contribution, the analysis of a semilinear abstract DAE of the form (1.1a). We introduce the concept of matrix-induced linear operators, dene appropriate solution spaces, and prove existence and uniqueness of a solution. The work of this chapter can be seen as a continuation and an addition

to the research done by Tischendorf [119] and Matthes [86], but is also related to [9, 128].
In Chapter 3, we give an introduction into the topic of second order hyperbolic equa- tions. We present certain general techniques for the analysis of such equations, we highlight characteristic features, and we apply these results to the special case of the prototypical linear wave equation. This serves as a justication to use Equa- tion (1.1b) as a representative of a larger class of second order hyperbolic PDEs.

# Chapter 4 is dedicated to our second main contribution. First, we provide a suitable framework for a related coupled system of abstract ODE and wave equation, and we provide existence and uniqueness results under specic assumptions on the coupling functions φ₁ and φ₂. Afterwards, we transfer the results obtained to coupled systems of the form (1.1).

Finally, in Chapter 5, we take a rst step into an optimal control problem where the coupled system of abstract ODE and wave equation related to (1.1) serves as a restriction. We are able to show the existence of an optimal control and a global minimizer for a specic cost functional. We do not derive rst or higher order conditions.
This thesis is complemented by three appendices. In Appendix A, we recall the intri- cate relation between certain matrix factorizations, generalized inverses of matrices, and projections onto and along certain subspaces. In Appendix B, we collect tools and knowledge from functional analysis, in particular from the theory of Bochner spaces. In Appendix C, we recall existence results for abstract dierential equations and operator equations.
##### Citation and Notation
Our aim is to make this thesis as consistent as possible to provide for a pleasant lecture. This applies to citations as well, which is why most statements we took from literature are not cited verbatim. Nevertheless, we always indicate where a certain statement can be found.
Throughout this thesis, [0,T] ⊂ R always denotes a nite time interval with T > 0. The dimension of the spatial domain Ω ⊂ R d is consistently denoted with d ∈ N. The solution variable for ODEs and DAEs is u; the solution variable for PDEs is usually v. If u is vector-valued, it maps either to R n or R r. The specic meanings of the natural numbers n ∈ N and r ∈ N will become clear in Chapter 2.
A general Banach space is denoted by (X, ‖·‖X). Following [124], we denote the dual space of X with (X ′, ‖·‖X′). We use |·| exclusively for the Euclidean norm in the nite-dimensional vector space R n. In all other cases, also for general Hilbert spaces, the norm is denoted by ‖·‖. We indicate the specic norm by a subscript; the only
##### <u>1 Introduction</u>
exceptions to this rule are matrix norms which have to do without. The transpose of a matrix A is denoted by A T.
A general Hilbert space is denoted by (H, (·, ·)). We explicitly distinguish between dual pairings 〈·, ·〉Xand inner products (·, ·)H. If unambiguous, we drop the sub- script for dual pairings and inner products. This holds true also and in particular when we use Gelfand triples (X,H,X ′ ), see Denition B.2.
If a Banach space X is embedded in another Banach space Y, we write X ֒→ Y. In this thesis, embeddings are always topological embeddings, i. e. they are injective and continuous. If an embedding is dense or compact, we do not use a specic notation but rather write it out explicitly.
Given a function v : [0,T] → X, we denote with v ′ its rst derivative with respect to time. Since we do not identify certain Lebesgue-Bochner spaces with Lebesgue spaces, for instance, we always write L²(0,T; L²(Ω)) and never L²((0,T) × Ω), the notation for the time derivative is unambiguous. Other partial derivatives or normal derivatives are written out explicitly. In this thesis, in particular when using Sobolev spaces or Bochner spaces of weakly dierentiable abstract functions, we avoid the use of distributional derivatives. For our purposes, the notion of weak derivatives is suciently general.
Apart from the common abbreviations, we only use two more. In formulas, we write
f. a. a. instead of “for almost all”, and we use a. e. instead of “almost everywhere”. Finally, we would like to explain one specic notational decision. Throughout this thesis, we collect necessary assumptions separately. This permits to simply refer to these assumptions at the beginning of denitions, theorems, and so on. It also helps to keep the assertions concise, and it allows to base one assumption upon another. Therefore, we decided to number the assumptions consecutively without referring to the chapter in which the assumption rst appeared. Unfortunately, this makes our assumptions harder to nd, which is why we provided a list of assumptions directly subsequent to the table of contents. We conclude the introduction by stating the rst and most fundamental assumption which is supposed to hold throughout the entire thesis. **Assumption 1.** Let [0,T] ⊂ R be a given xed time interval with T > 0, and let Ω⊂R d be an open interval for d = 1, and a Lipschitz domain for d ∈ {2, 3}, see Denition B.10.
#### 2 Analysis of an Abstract Semilinear DAE
##### Introduction to Dierential-Algebraic Equations
Dierential-algebraic equations (DAEs) are, beside ordinary dierential equations (ODEs) and partial dierential equations (PDEs), a third type of dierential equa- tions. There are various dierent perspectives on DAEs and their extensions but perhaps the most common way to understand them is as *constrained* dierential equations. If the dynamical behavior of a physical system is described by an ODE but the state of this physical system is subject to certain algebraic constraints, DAE systems arise. Such algebraic constraints appear naturally in many elds of applica- tions. In ow networks, for instance the gas ow through a pipe network, electrical circuits, or the blood ow through the cardiovascular system, such algebraic con- straints emerge in the form of Kirchho’s Laws. Consequently, ow networks can be eciently modeled by DAEs [41, 42, 119], [47, 87, 111]. But DAEs and their extensions are also widely used to describe and model mechanical multibody sys- tems which appear in aerospace engineering or robotics [12, 112, 114], or problems in chemical engineering [25]. DAEs also appear as reduced models in singular pertur- bation theory [59], or when semidiscretizing multiphysics systems, see for instance [9, 11, 118, 128].
**Notions of DAEs** Due to their ubiquity, there is nowadays a large variety of terms describing DAEs and their extensions. Terms like *abstract DAEs*, *operator DAEs*, *constrained PDEs*, *Partial Dierential-Algebraic Equations* (PDAEs), and more all describe, in general, some form of constrained dierential equation but vary depend- ing on the context in which they appear and the mathematical framework in which they are stated. Unfortunately, there is no unanimous agreement on what term de- scribes what kind of equations, and so, in order to facilitate the integration of the abstract DAE analyzed in this chapter into the existing research literature, we would like to clarify these terms for the scope of this thesis.
In general, DAEs can, similar to ODEs, be formally understood as equations of the form f (t,u(t),u ′
(t)) = 0. (2.1)
Equation (2.1) is called a DAE if a), and similarly to ODEs, it holds in a nite- dimensional vector space such as R n, and b), and in strict contrast to ODEs, the partial derivative of f with respect to the third variable is supposed to be a singular
<u>2 Analysis of an Abstract Semilinear DAE</u>
matrix; see [72, p. xix, 97]. In particular, throughout literature the term “DAE” is used to refer to a constrained ordinary dierential equation in a nite-dimensional setting. In this setting, we commonly expect solutions to be dierentiable in the classical sense.
In contrast to DAEs, abstract DAEs, or synonymously operator DAEs, refer to constrained dierential equations in an innite-dimensional setting. Here, we usually look for solutions with a dierent type of regularity than for DAEs. In particular, we do not expect the solution to be classically dierentiable neither with respect to spatial variables nor with respect to time. The term “PDAE” was coined by Simeon and Arnold [114] and initially used to refer to coupled systems of PDEs and DAEs; see also [12, 13]. Nowadays, PDAEs comprise also constrained PDEs as a special case such as the incompressible Navier-Stokes Equations, see [113, pp. 29 sq.]. The analysis of abstract DAEs and PDAEs, their numerical treatment, and their applications are part of current and ongoing research, see for instance [9, 40, 62, 86, 128].
**Properties of Solutions to DAEs** As mentioned above, a DAE is a constrained ordinary dierential equation; however, it is not obvious which part of a given DAE describes the inherent dynamics and which part belongs to the constraining non- dynamical part. To illustrate this, consider formally the exemplary system  ′  u¹
(t) = u₂(t) + r(t),
u ′ 3
(t) = u₁(t),
  u₁(t) = g(t),
with solution variables u₁,u₂,u₃ and right-hand side functions g and r. At rst sight, it looks as if the rst two equations described the dynamical part of this DAE, and the third equation were the constraint. However, the unique solution is given through ∫t u₁(t) = g(t), u₂(t) = g ′
(t) − r(t), and u₃(t) = u₃(t₀) + g(s) ds.
t₀
So, the dynamics of the DAE are determined entirely by u₃ and by means of only one and not two equations. Only for the third component u₃, it is possible to prescribe initial values. Moreover, in order to solve this DAE, it is necessary not only to integrate but also to dierentiate the right-hand side function g. Therefore, the right-hand side functions of a DAE usually have to be more regular than the right-hand side functions of ODEs. Since on the other hand solutions to DAEs may also depend on derivatives of the right-hand side functions, they may show a more unstable behavior.
Due to these considerations we will distinguish carefully between *dierentiable*, *dif-* *ferentiated*, and *dynamical* variables. The dynamical variables of the DAE are the
ones describing the inherent dynamics; this would be u₃ in our example. A dier- entiated variable is a variable which appears in a dierentiated way in the DAE. In our example, derivatives of both u₁ and u₃ appear, and thus both are dieren- tiated variables. Finally, depending on the context or the framework in which we discuss the DAE, a variable that is neither dynamical nor dierentiated may still be dierentiable. For instance, u₂ is dierentiable if g and r are suciently smooth.
Although the example above is stated in a DAE way, it is clear that our deliberations translate to the innite-dimensional framework and thus to solutions for abstract DAEs and PDAEs. There, it is generally just as necessary to distinguish between dynamical, dierentiated, and dierentiable parts of the solution. For the analysis of the abstract DAEs discussed in this chapter, we will be particularly mindful of this.
##### Overview and Literature
The main objective of this chapter is to analyze the abstract semilinear DAE
(E u) ′
(t) + φ(t,u(t)) = q(t) for 0 ≤ t ≤ T. (2.2)
Here, E is a matrix-induced linear operator, see Section 2.1, and φ is a nonlinear continuous mapping. The right-hand side function q is allowed to be discontinuous. Equation (2.2) is supposed to hold in a Banach space. In view of dierent notions of solutions existing for abstract dierential equations stated in innite-dimensional function spaces, we are interested in strong solutions. Following [39, Chapter 7, 95,
p. 109], we call strong solution a solution that is continuous, dierentiable almost ev- erywhere, and has an integrable time derivative. This notion has to be distinguished from classically dierentiable solutions, mild solutions which appear in semigroup theory, see [95], as well as weak solutions, and distributional solutions, the last two known from standard PDE theory. Confer for instance [108, pp. 51 sq.]. This chapter is organized as follows. In Section 2.1, we introduce the concept of matrix-induced linear operators. They are linear and bounded operators that act pointwise almost everywhere like matrices. The concept itself is not novel; however, the restriction to operators of this specic type in the abstract DAE context allows on one hand to transfer quite naturally decoupling strategies that work for DAEs to the innite-dimensional setting. On the other hand, we do not deem this restric- tion exceedingly critical since these operators appear very frequently in applications. Further, many examples given in recent research literature implicitly use this type of operators; compare for instance the examples given in [86, 128]. Also, matrix- induced linear operators directly fulll specic algebraic assumptions that otherwise need to be explicitly stated. In Section 2.2, we introduce an appropriate functional analytical setting in which we can understand DAE (2.2). We also show that DAE (2.2) can always be rewritten
<u>2 Analysis of an Abstract Semilinear DAE</u>
as a properly stated abstract DAE. The notion of properly stated DAEs is taken from [72] and goes back to fundamental work by Balla and März [15] and März [85]. Rewriting the DAE in such a way allows for an analysis with lowest possible smoothness demands; cf. [72, p. 51].
In Sections 2.3 and 2.4, we present a decoupling technique to separate the dynamical components of the solution from the non-dynamical ones and to nd the inherent dynamical and the complementing algebraic equations. Our decoupling procedure is based on the dissection approach introduced by Jansen [64], which in turn is related to the tractability concept of [72] and the strangeness concept of [71]. The dissection approach is transferred to work in our innite-dimensional setting. In Section 2.4, we also present with Theorem 2.20 a novel theoretical result that allows, under specic assumptions on the nonlinear function φ, to express the non-dynamical variables as a function of the dynamical variables. In other words, Theorem 2.20 provides an index-1-like criterion for the abstract DAE (2.2). We then can solve the dynamical equations, the inherent ODE, with respect to the dynamical variables, afterwards recover the non-dynamical variables, and dynamical and non-dynamical variables together form a solution to our abstract DAE. We close this chapter with a discussion in Section 2.5.
There exists a considerable amount of literature on the theoretical fundamentals of DAEs. The textbooks by Kunkel and Mehrmann [71] and Lamour, März, and Tis- chendorf [72] are excellent starting points into the world of DAEs. Both include very well-written introductions into the topic, many examples, and many bibliographical references. The signicant textbooks on the numerical solution of DAEs by Brenan, Campbell, and Petzold [21] and Hairer, Lubich, and Roche [58], and the seminal paper by Petzold [97] should not go unmentioned. In [113] the modern history of DAE research is presented legibly and enjoyably. In [85], DAEs are discussed from a functional analytical point of view which is particularly interesting in view of ab- stract DAEs. All of these publications discuss mainly or exclusively DAEs in a nite-dimensional setting.
PDAEs and more general abstract DAEs are part of ongoing research. As such sys- tems do arise out of very dierent contexts, they are often discussed by means of very dierent techniques which makes for a challenging comparison. In [2, 4–6, 16, 119] PDAEs are discussed in the context of electrical circuits connected to semicon- ductors, diodes, or electromagnetic components. In these articles, a modied nodal analysis of the electrical circuit leads to a DAE and the diodes or semiconductors are described by PDEs. In the context of exible multibody systems, PDAEs were analyzed in [12, 13, 114], and the modeling of such PDAEs and their numerical treatment is elaborately discussed in the monograph by Simeon [112].
Abstract DAEs can be interpreted as a generalization to PDAEs. Their structure is often more general as it does not necessarily take the form of a coupled system of PDE and DAE. In [119], abstract DAEs with monotonicity properties are discussed. A general functional analytical framework and possible discretizations are presented
<u>2.1 Matrix-induced Linear Operators</u>
here. In [86], this work is continued and existence results for such systems are developed. These abstract DAEs can be understood as a generalization of the circuit- eld PDAEs from electrical engineering we mentioned before. A general framework for abstract DAEs arising from uid dynamics is discussed in [40]. Such systems include notably linearizations of certain Navier-Stokes equations. In [9, 10, 128], abstract DAEs with semiexplicit structures or saddle point structures are analyzed in quite general functional analytical frameworks. Also various discretizations and numerical methods for solving such systems are discussed.
The abstract semilinear DAE (2.2) which we analyze in this chapter is comparable to abstract DAEs of the form
A ∗ (Du) ′
(t) + B(t)(u(t)) = r(t)
which are discussed in [86, 119]. Such abstract DAEs are understood in a variational sense. The linear operators A, D, and B are more general than the matrix-induced linear operator E of (2.2). In particular, B may be a dierential operator, e. g. the spatial Laplacian −∆. However, the operators A and D are also more specic in the sense that A has essentially to be the adjoint of D. This is not required in our thesis; cf. Section 2.2. Moreover, D has to meet certain structural assumptions, see [119,
p. 70, 86, p. 58], which are automatically met by matrix-induced linear operators. The analysis presented in [86] follows closely the analysis of abstract ODEs given in [126, Chapter 23, 127, Chapter 30]. In particular, the operator B needs to possess the typical monotonicity properties to apply the Theorem by Browder and Minty, see [127, Chapters 26 and 30]. For the analysis of system (2.2), we make use of a certain monotonicity assumption, too. However, the nonlinear function φ essentially needs to be monotone on a specic subspace only due to our novel theoretical result Theorem 2.20 in Section 2.4. As mentioned before, the abstract DAEs analyzed in [9, 10] have a semiexplicit structure. The explicitly given algebraic constraint is incorporated by means of a certain Lagrangian method. This is quite dierent to our approach and notably the abstract DAE (2.2) is not required to have a semiexplicit structure. In [128], abstract DAEs with a saddle-point structure are analyzed. Such a structure arises in particular out of the Lagrangian method applied to the abstract semiexplicit DAEs of [9, 10]. The abstract DAEs of [128] are linear although they allow for certain time-dependent operators which would correspond to the operator E being time- dependent. For (2.2), we assume E to be constant in time.
##### 2.1 Matrix-induced Linear Operators
In this section, we introduce the concept of matrix-induced linear operators. So far these kinds of operators have not been discussed in literature although they seem to be a tting tool to discuss Banach space valued DAEs. This holds in particular
<u>2 Analysis of an Abstract Semilinear DAE</u>
for abstract DAEs that arise out of network structures like ow networks. But also in view of coupling dierent types of dierential equations like in multiphysics systems, such operators promise to be useful. It seems only appropriate to exploit the algebraic structure which is inherent to networks, graphs, and systems of dierent types of dierential equations, and we believe that matrix-induced linear operators are well-suited for this purpose. Perhaps not very surprisingly, it turns out that many benign properties matrices possess can be transferred to matrix-induced linear operators, and thus, analytical tools which are known for DAEs should be more easily transferable to abstract DAEs whenever matrix-induced linear operators appear.
In the following, we dene matrix-induced linear operators between Lebesgue and Bochner spaces. The presentation is tailored to the search for strong solutions of DAE (2.2).
**Denition 2.1 (Matrix-induced Linear Operator between Lebesgue Spaces).** Let
|ij|m×n|||
|---|---|---|---|
|||p|m|
|p|n|||
|||n 1j|j|
|||j=1||
|||n nj|j|
|||j=1||
a matrix E := (e)∈R be given. For xed 1 ≤ p ≤ ∞, we associate to E the linear and bounded operator
E : L p (Ω, R n )→L (Ω, R), (2.3)
dened for u ∈ L (Ω, R) through   ∑  e u (x)     .  (E u)(x) := E · u(x) = .. , (2.4)   ∑   e u (x)
where the multiplication of E with u(x) is meaningful for almost all x ∈ Ω.
**Remark.** The linearity of E is obvious, and E is bounded (continuous) since
(∫)1/p(∫)1/p
‖E u‖Lp(Ω,Rm):= |Eu(x)| p dx ≤ ‖E‖ p |u(x)| p dx = ‖E‖‖u‖Lp(Ω,Rn). Ω Ω (2.5) Here, |·| denotes the Euclidean norm in R m or R n, and ‖E‖ is the corresponding induced matrix norm of E.
As common for linear bounded operators, we can lift the considerations to Bochner spaces. To this end, recall that for any Bochner-integrable function u : [0,T] → L p (Ω, R n ) and linear operator E, the mapping t 7→ (E u)(t) := E u(t) is Bochner- integrable, too. We refer to Appendix B.3 for more information and relevant litera- ture; see in particular Theorem B.17.
<u>2.1 Matrix-induced Linear Operators</u>
**Denition 2.2 (Matrix-induced Linear Operator between Bochner Spaces).** Let
E : L p (Ω, R n )→L p (Ω, R m )
be a matrix-induced linear operator between Lebesgue spaces, see Denition 2.1. Then, we can dene in a canonical way a linear and bounded operator
E : L p (0,T; L p (Ω, R n )) → L p (0,T; L p (Ω, R m )), (2.6)
denoted with the same symbol, through (E u)(t) := E u(t) for u ∈ L p (0,T; L p (Ω, R n )). Additionally, it holds ∫t 1 ∫t 1 E u(t)dt = E u(t) dt (2.7) t₀ t₀ for any t₀,t₁ ∈ [0,T].
**Remark.** The linearity of the operator E given through (2.6) is again obvious, and by (2.5)
(∫)1/p T
p ‖E u‖Lp(0,T;Lp(Ω,Rm))=
||‖E u(t)‖||dt||||
|---|---|---|---|---|---|---|
|L (0,T;L||L (Ω,R|)||||
||0 T|||/|||
|||p L (Ω,R|)||L (0,T;L|(Ω,R))|
||0||||||
Lp(Ω,Rm)
(∫)1 p p
≤ ‖E‖ ‖u(t)‖p mdt = ‖E‖‖u‖ p p n.
(2.8) holds. This shows the boundedness of E given by (2.6). Equation (2.7) is a special case of a more general result stated and proved in [39, pp. 156 sqq.].
The appeal of matrix-induced linear operators lies in the possibility to transfer many nice properties matrices possess to these kind of operators. They allow for example for generalized inverses. In view of our dissection-based decoupling strategy laid out in Section 2.3, we would like to point out that linear operators induced by projection matrices are also projections, i. e. they are linear and idempotent, but moreover, they are continuous. Note that in Banach spaces projections onto subspaces do not need to be continuous; in fact, a notable result by Lindenstrauss and Tzafriri [80] states that in any Banach space which is not isomorphic to a Hilbert space, there are closed subspaces which are not image of a continuous projection operator; cf. [23, p. 39].
Next, we present some of the properties of matrix-induced linear operators. We focus particularly on those that will be used later in this thesis. But before, we recall the concept of generalized inverses for linear operators. For matrices, the notions of gen- eralized inverses in general and Moore-Penrose inverses in particular are well-known. Also, the strong relationship between generalized inverses and projections is thor- oughly understood in this case, and we refer to Appendix A and the textbooks cited
<u>2 Analysis of an Abstract Semilinear DAE</u>
therein for more information. But for linear operators, this is a topic which is rarely discussed in standard textbooks on linear functional analysis. In view of abstract DAEs and specically the projection-based decoupling procedure proposed by Lam- our, März, and Tischendorf [72], generalized inverses of linear operators promise to be a highly interesting tool for the analysis of certain types of abstract DAEs stated in innite-dimensional function spaces. To the best of our knowledge, gen- eralized inverses for linear operators between general topological vector spaces were rst examined by Nashed [89, 90], Nashed and Votruba [91, 92], and Ben-Israel and Greville [17]. Their connection to normally solvable operators was also investigated in [89], and normally solvable operators can be linked to DAEs as demonstrated in the survey by März [85].
**Lemma 2.3.** *Let two matrices* E∈R k×n *and* F ∈ R m×k *as well as their respective* *induced linear operators*
|k|p|m|
|p|n|p|
|||m×n|
E : L p (Ω, R n )→L p (Ω; R k ) *and* F : L p (Ω, R)→L (Ω; R)
*be given as in Denition 2.1. Then, the composition* F ◦ E : L (Ω, R)→L (Ω, R m ) *coincides with the linear operator induced by the product matrix* F·E∈R*.*
**Proof.** By denition, it holds for u ∈ L p (Ω, R n ) and for almost all x ∈ Ω
((F ◦ E)u)(x) = (F (E u))(x) = F · ((E u)(x)) = F · (E · u(x)) = (F · E) · u(x).
In other words, the mapping E 7→ E that assigns to a matrix its corresponding induced linear operator is structure-preserving. Observe that this result can be sharpened if we consider only matrices E ∈ GLn(R). Then, the mapping E → E is a group isomorphism between (GLn(R), ·) and the set of invertible matrix-induced linear operators, equipped with usual law of composition. See also Corollary 2.6 below.
**Denition 2.4.** Let X and Y be two Banach spaces, and let E ∈ L(X,Y). An operator E − ∈ L(Y,X) is called an *(algebraic) generalized inverse of* E if it satises
EE − E=E and E − EE − = E −
. (2.9)
In other words, E − is an *inner* as well as an *outer inverse*.
**Lemma 2.5.** *Let* E∈R m×n *be a matrix and denote with* E : L p (Ω, R n )→L p (Ω, R m ) *its corresponding induced linear operator as in Denition 2.1. Let* E − ∈ R n×m *be* *a xed generalized inverse of* E*. Then, the linear operator* E − *induced by* E − *is a* *generalized inverse of* E*.*
<u>2.2 Solution Spaces for Semilinear Abstract DAEs</u>
**Proof.** The result follows from Lemma 2.3. In fact, by Denition A.1, E and E −
satisfy
EE − E=E and E − EE − = E −.
Consequently, for u ∈ L p (Ω, R n ) and for almost all x ∈ Ω, it holds by Lemma 2.3
(EE − E u)(x) = (EE −
E)u(x) = Eu(x) = (E u)(x).
In other words: E − is an inner inverse of E. Analogously we show that E − is an outer inverse. Thus, the linear operator E − induced by the matrix E − is a generalized inverse to E in the sense of Denition 2.4.
**Corollary 2.6.** *If a square matrix* E ∈ R n×n *is invertible, its corresponding in-* *duced linear operator* E ∈ L(L p (Ω, R n )) *is invertible, as well. Its inverse* E −1 ∈ L(L p (Ω, R n )) *is induced by the inverse* E −1 *of* E*.*
**Lemma 2.7.** *Let* P ∈ R n×n *be a projection matrix. Then, the corresponding linear* *operator* P ∈ L(L p (Ω, R n )) *induced by* P *is a linear and continuous projection, and* *it holds* L p (Ω, R n ) ≃ ker P ⊕1im P. (2.10)
*This is to say that* L p (Ω, R n ) *is topologically isomorphic to the (algebraic) direct* *sum* ker P ⊕ im P*, equipped with the product* 1*-norm.*
**Proof.** A similar proof is given in [85, Lemma 6.10, p. 87].
The projection property of P follows directly from the projection property of P by means of Lemma 2.3. Besides, matrix-induced linear operators are always continu- ous, and this already implies that ker P and im P are closed and that (2.10) holds. In fact, all linear and bounded projections on normed spaces have this property. See [124, Lemma IV.6.1, p. 178].
##### 2.2 Solution Spaces for Semilinear Abstract DAEs
In this section, we introduce the appropriate solution spaces for the abstract semi- linear DAE (2.2) to be able to meaningfully discuss existence and uniqueness of solutions (2.2) in the subsequent Sections 2.3 and 2.4. The linear operator E is constant over time and thus the relation
E u ′ = (E u) ′
holds for dierentiable u. However, it is not sensible to look for dierentiable solu- tions to our abstract DAE (2.2) as illustrated by our introductory example on page 6.
<u>2 Analysis of an Abstract Semilinear DAE</u>
Eectively, it is not u but only E u that ought to be dierentiable. This motivates the denition of the specic function spaces below. We also show that (2.2) can always be transformed into an abstract DAE with properly stated leading term; see Denition 2.13 at the end of this section. Related notions have been introduced in [85, p. 86, 119, p. 71]; see also [86, p. 14].
|||n×n|
|p|n||
|1,p|p|1,p|
|E|||
**Denition 2.8.** Let Assumption 1 hold. Let E ∈ R be a matrix and E ∈ L(L (Ω, R)) its corresponding matrix-induced linear operator. We introduce {} n p p n p n W (0,T; L (Ω, R)) := u ∈ L (0,T; L (Ω, R)), E u ∈ W (0,T; L (Ω, R)).
(2.11)
In the case p = 2, we also write {} HE1(0,T; L²(Ω, R n )) := u ∈ L²(0,T; L²(Ω, R n )), E u ∈ H¹(0,T; L²(Ω, R n )).
(2.12)
Here, E u has to be understood as in Denition 2.2. Equipped with the norm
|‖u‖|:= ‖u‖||+ ‖(E u)|‖||(2.13)|
|---|---|---|---|---|---|---|
|1,p|p n|||||2|
|E|||′|′|E1||
|H|L (0,T;L|(Ω,R))||L (0,T;L|(Ω,R))||
||n||||||
|E1|||||||
W 1,pLp(0,T;Lp(Ω,Rn)) ′ Lp(0,T;Lp(Ω;Rn)) E n the space W (0,T; L (Ω, R)) is a Banach space. The space H (0,T; L (Ω, R)), equipped with the inner product
(u,v) 1 := (u,v) 2 2 n + ((E u), (E v)) 2 2 n, (2.14) E
where u,v ∈ H (0,T; L²(Ω, R)), is a Hilbert space.
**Proof.** We shall prove that the dened spaces are indeed Banach respectively Hilbert spaces. A similar proof is given in [85, Lemma 6.9, pp. 86 sqq.].
It is clear that (2.13) denes a norm and that (2.14) denes a scalar product. We only show completeness.
(k) 1,p p n (k)
Let (u)⊂W E (0,T; L (Ω, R)) be a Cauchy sequence. Then (u) and by conti- nuity of E also (E u
(k) ) are Cauchy sequences in L
p (0,T; L p (Ω, R n )). Consequently, there exists some u ∗ ∈ L p (0,T; L p (Ω, R n )) such that
(k) ∗
|‖u − u|‖||→ 0 and|‖E u|− E u|‖||→ 0.|
|---|---|---|---|---|---|---|---|---|
|(k)|∗ ∗ ∗|1,p (k) 1,p|p n ∗ W p|1,p (0,T;L n|p (Ω,R))|n ∗ 1,p||p|
|||||||E|||
Lp(0,T;Lp(Ω,Rn))
(k) ∗ Lp(0,T;Lp(Ω,Rn))
But (E u) is also a Cauchy sequence in W (0,T; L (Ω, R)) by (2.13). Therefore, there is some w ∈ W (0,T; L (Ω, R)) such that
‖E u − w ‖ 1,p p n → 0.
n We deduce E u = w ∈ W (0,T; L (Ω, R)), and thus u ∈ W (0,T; L (Ω, R))<u>.</u>
<u>2.2 Solution Spaces for Semilinear Abstract DAEs</u>
The declaration of these function spaces is sucient to gain a rst intuition for DAE (2.2). It is most important to keep in mind the dierence between dierentiable, dierentiated, and dynamical parts of u. Whether all of u or only part of it is dierentiable, depends on the specic framework of the DAE and the regularity of the right-hand sides. However, if the null space of E is not trivial, then some part of u may lie in this null space. As a consequence, the derivatives of this part do not appear in our abstract DAE (2.2). In other words, this part of u does not belong to the dierentiated components, let alone the dynamical components describing the inherent dynamics of the abstract DAE. It is therefore important to analyze the null space of E, and for this we introduce a specic factorization of E leading to a DAE with properly stated leading term. For more illustrating examples, we refer to [72, pp. 50 sqq., 58 sqq.].
##### Well-matched Factorization and Properly Stated Leading Term
To tackle the problem of revealing dierentiated and non-dierentiated components of our DAE solution function u, we try and rewrite our abstract DAE (2.2) in a specic way. One possibility is to factorize the linear non-invertible operator E into two linear operators which are well-matched in a certain sense. The notion of well- matched factors and the role they play for the analysis of DAEs stated in a nite- dimensional setting is given in Appendix A. Below, we translate this framework to abstract DAEs with matrix-induced linear operators. For general linear operators between innite-dimensional spaces this is, in general, not possible without further assumptions due to the fact that algebraic direct sums are not necessarily topological direct sums. This is connected to the result by Lindenstrauss and Tzafriri [80] mentioned above. Confer also [91, pp. 827 sq.].
**Assumption 2.** We assume that the matrix E ∈ R n×n is singular and we denote with r := rank E < n the rank of E.
**Denition 2.9.** Let Assumptions 1 and 2 hold, and denote with E ∈ L(L p (Ω, R n )) the linear operator induced by matrix E of Assumption 2. Recall that rank E = r. We call two matrix-induced linear operators
A : L p (Ω, R r )→L p (Ω, R n ) and D : L p (Ω, R n )→L p (Ω, R r )
*well-matched factors of* E if the equality E = AD holds, and A and D fulll the *topological transversality condition*
L p (Ω, R r ) ≃ ker A ⊕1im D. (2.15)
In other words: The space L p (Ω, R r ) is topologically isomorphic to the algebraic direct sum ker A ⊕ im D equipped with the product 1-norm.
<u>2 Analysis of an Abstract Semilinear DAE</u>
**Remark.** Denition 2.9 is specically tailored to matrix-induced linear operators because this is the predominant kind of operators we use throughout this chapter. Without eort, this denition may be extended to general linear operators between Banach spaces; cf. also [86, p. 13].
Denition 2.9 corresponds to the case of well-matched full-rank factors in Deni- tion A.6.
**Theorem 2.10.** *Let Assumptions 1 and 2 hold, and let* E ∈ L(L p (Ω, R n )) *be the lin-* *ear operator induced by* E∈R n×n *. Then, there exists a well-matched factorization* E = AD *in the sense of Denition 2.9.*
**Proof.** By Lemma A.9, there are matrices A ∈ R n×r and D ∈ R r×n that are well- matched full-rank factors for the matrix E in the sense of Denition A.6. Thus, it holds E = AD, and the transversality condition (A.4) is satised. Denote the linear operators induced by A and D with A and D correspondingly. Then, E = AD by Lemma 2.3.
It remains to show the validity of the topological transversality condition (2.15). To this end, we rst observe that ker A = {0}. This holds since the inducing matrix A∈R n×r has rank r, and thus ker A = {0} by the Rank-Nullity Theorem. Now, let u˜ ∈ ker A ⊂ L p (Ω, R r ). We have ∫ p n p Au˜ = 0 ∈ L (Ω, R) ⇐⇒ |Au˜(x)| dx = 0. Ω
The latter holds if and only if Au˜(x) = 0 almost everywhere in Ω. Since the null space of A is trivial, this means u˜(x) = 0 almost everywhere, thus u˜ = 0 in the sense of L p (Ω, R r ).
||p|r|||
|---|---|---|---|---|
||−|p|r p|n|
|− −|||−|p|
||r − −|p −|r||
If we can show that im D = L (Ω, R) holds, (2.15) is proved. By Lemma 2.5, D allows for a generalized inverse D : L (Ω, R)→L (Ω, R) with corresponding generalized inverse D of D. The composition DD ∈ L(L (Ω, R r )) is induced by the matrix product DD, see Lemma 2.3, but by Lemma A.10 the matrix DD − is actually the identity matrix in R. Consequently, by denition of matrix-induced linear operators, we have for DD, all u˜∈L (Ω, R), and almost all x ∈ Ω that
(DD u˜)(x) = DD u˜(x) = u˜(x)
which is equivalent to
DD − = id ∈ L(L p (Ω, R r )). (2.16)
On the other hand, we have rather obviously im DD − ⊂ im D. Putting the pieces together, we have
L p (Ω, R r ) = im DD − ⊂ im D ⊂ L p (Ω, R r ),
<u>2.2 Solution Spaces for Semilinear Abstract DAEs</u>
and we obtain im D = L p (Ω, R r ).
**Remark.** Theorem 2.10 only provides one way to obtain well-matched factors of a given matrix-induced linear operator E. It does not state, however, that a given well-matched factorization of E has to be constructed necessarily from well-matched full rank factors A and D of the E inducing matrix E.
In summary, we have proved that for matrix-induced linear operators, there exists always a factorization with two other matrix-induced linear operators which, in a sense, split the pivot space L p (Ω, R r ) of (2.15), that is the domain space of the rst and the image space of the second factor, in a trivial way. Although Theorem 2.10, as stated here, is a non-constructive existence result, observe that computing such a well-matched factorization is essentially not more expensive than computing the singular value decomposition of the inducing matrix E; see Lemma A.9.
We have yet to justify why such a factorization is useful. This will hopefully become clear in the following section where we look at the decoupling procedure assiduously. But for now, let us close this section with an indication towards its advantages.
**Lemma 2.11.** *Let Assumptions 1 and 2 hold, and let* E ∈ L(L p (Ω, R n )) *be the linear* *operator induced by* E∈R n×n *. Let* A∈R n×r *and* D∈R r×n *be well-matched full-* *rank factors of* E *as in Denition A.6, and denote with* A *and* D *the corresponding* *induced linear operators. Then, it holds* ker E = ker D *and* im E = im A*.*
**Proof.** By Lemma A.7, it holds ker E = ker D. The result ker E = ker D follows immediately by denition of matrix-induced linear operators.
⊂ im A is clear.
|The rst relation im E||For the second relation, let u ∈ im A ⊂||
|---|---|---|---|
|p n|p −|r p|r|
|||− −|−|
L (Ω, R). Then, there exists u˜ ∈ L (Ω, R) with Au˜ = u. As in the proof of Theorem 2.10, it holds that DD = id ∈ L(L (Ω, R)) where D − is a generalized inverse of D induced by a generalized inverse D of D. Thus, we have DD − u˜ = u˜. But then u = Au˜ = A(DD u˜) = ED u˜.
Thus, u ∈ im E and the images of E and A coincide.
**Theorem 2.12.** *Let Assumptions 1 and 2 hold, and let* E ∈ L(L p (Ω, R n )) *be the lin-* *ear operator induced by* E∈R n×n *. Let* A∈R n×r *and* D∈R r×n *be well-matched* *full-rank factors of* E *as in Denition A.6, and denote with* A *and* D *the corre-* 1,p p n *sponding induced linear operators. Then, the function space* W E (0,T; L (Ω, R))
<u>2 Analysis of an Abstract Semilinear DAE</u>
*of Denition 2.8 coincides topologically with the function space* {}
|1,p|p n|p n|p r|
|---|---|---|---|
|D||||
p 1,p W (0,T; L (Ω, R)) := u ∈ L (0,T; L (Ω, R)), Du ∈ W (0,T; L (Ω, R)). (2.17) *In other words: The norms* ‖·‖ W 1,p *and* ‖·‖ W 1,p *dened as in or analogously to* (2.13) E D *are equivalent.*
**Proof.** A similar proof is given in [85, Lemma 6.9, pp. 86 sq.].
are matrices, have uniquely determined Moore-Penrose in-
|Since|D and E|they|
|||+|
|+|n×n|n×n|
|+|+||
verses which we denote with D and E + respectively. By Proposition A.5, both D D∈R and E + E∈R are the respective uniquely determined orthogonal projections along ker D and ker E. But both null spaces coincide, so the equation D D=E E holds.
This implies the relation
||+ +||
|+ +||+ +|
D = DD D = DE E (2.18)
by Lemma 2.3 where D and E are the linear operators induced by D and E respectively. Note that by Lemma 2.5 these are generalized inverses of D and E in the sense of Denition 2.4 but they are most certainly not generalized Moore-Penrose inverses; see the remark subsequent to this proof. From this relation and (2.8) we deduce
‖Du‖W1,p(0,T;Lp(Ω,Rn))= ‖DE + E u‖W1,p(0,T;Lp(Ω,Rn))
≤ ‖DE + ‖‖E u‖W1,p(0,T;Lp(Ω,Rn)).
1,p p n 1,p p n This shows that W E (0,T; L (Ω, R)) ⊂ W D (0,T; L (Ω, R)) holds and it provides the rst inequality necessary for proving the equivalency of norms. The second inclusion 1,p p n 1,p p n W D (0,T; L (Ω, R)) ⊂ W E (0,T; L (Ω, R))
as well as the second inequality for proving equivalency of norms follows analogously.
**Remark.** For the proof of Theorem 2.12, we made use of the fact that matrices have a uniquely determined Moore-Penrose inverse. This is crucial when exchanging D + D for E + E to prove the relation (2.18). However, general linear and possibly unbounded operators between Banach spaces do not possess such a Moore-Penrose inverse, let alone a unique one. Even for linear operators between Hilbert spaces this does not hold. See [17, Section 9.3, pp. 336 sq.], and also [92] for the even more general concept of *orthogonal partial inverses*.
<u>2.3 Dissection-based Decoupling Procedure</u>
In this section, we gured out appropriate solution spaces for the abstract DAE (2.2), and we pinned down requirements that are sucient to rewrite this equation in a meaningful way. In fact, using the right kind of factorization for E, Lemma 2.11 and Theorem 2.12 ensure that (2.2) is equivalent to
A(Du) ′
(t) + φ(t,u(t)) = q(t) f. a. a. t ∈ [0,T]. (2.19)
|||1,p|p n|
|---|---|---|---|
|1,p E|p n|D||
Moreover, this allows to look for solutions in the space W (0,T; L (Ω, R)) instead of W (0,T; L (Ω, R)).
This is a fruitful rst step to separating dierentiated from non-dierentiated parts of a possible solution function u: It shows that the dierentiated part of u needs to lie in the image of D. In the next section, we discuss a decoupling procedure for abstract DAEs of type (2.19) that makes extensive use of the additional properties that a suitable factorization provides. To this end, we summarize this notion in the form of the following denition.
**Denition 2.13.** Let Assumption 1 hold. Let A and D be two well-matched factors as in Denition 2.9 which are induced by well-matched full-rank matrices A ∈ R n×r
and D ∈ R r×n with r < n. Then, we call (2.19) an *abstract DAE with properly* *stated leading term*, or *properly stated* for short.
##### 2.3 Dissection-based Decoupling Procedure
We now arrive at a point where we are able to present our procedure for decoupling the properly stated abstract DAE (2.19) and to introduce the matrix-induced linear operators that are necessary for this method. The decoupling itself, in particular the extraction of the underlying dynamical equations, consists of a twofold split- ting technique: We need to split the solution variable u into the dierentiated and non-dierentiated components. But we also need to separate the inherent dynamical equations from the complementing algebraic equations. To realize this, recall the introductory example from page 6  ′  u¹
(t) = u₂(t) + r(t),
u ′ 3
(t) = u₁(t),
  u₁(t) = g(t).
It is apparent that u₁ and u₃ are the dierentiated components, and thus the rst part of our splitting technique is trivial in this example. But as we have seen, only u₃ describes the inherent dynamics of this system, and nding the dynamical equations and separating them from the complementing algebraic equations would still need to be addressed by the second part of the splitting process.
<u>2 Analysis of an Abstract Semilinear DAE</u>
The decoupling procedure below is based on the dissection approach that was intro- duced by Jansen [64] to decouple DAEs. It is strongly inspired by the projection- based approach introduced by Lamour, März, and Tischendorf [72] but both decou- pling approaches have one striking dierence that can be illustrated most easily by the following consideration: Let x = (x₁,x₂)∈R² be a simple vector. On one hand, we consider projection matrices P,Q ∈ R 2×2 that project onto the two components such that x1 () Px = (0) and Qx =x0 2
. (2.20)
In other words, P is a projection on span{e₁} and Q is a projection on span{e₂}. Here, x = Px + Qx is split into two parts that have the same dimension as x itself. This splitting approach would be a projection-based one. On the other hand, we can dissect the vector x using matrices P˜,Q˜ ∈ R 1×2 with
P ˜ x = x₁ and Q˜ x = x₂. (2.21)
Obviously, P˜ and Q˜ are not projections as they are not idempotent, but in exchange the resulting right-hand sides are of lower dimension. If we step away from this example and transfer the ideas to the decoupling of a system of equations, it means that using a projection-based approach possibly results in a larger system of equa- tions, whereas the second approach, the dissection approach, retains the system’s size but loses the projection property of the splitting matrices involved.
After these preparatory remarks, we return to decoupling the abstract DAE
A(Du) ′
(t) + φ(t,u(t)) = q(t) f. a. a. t ∈ [0,T]. (2.19)
**Assumption 3.** Let Assumption 1 hold. Assume that the abstract DAE (2.19) has a properly stated leading term in the sense of Denition 2.13.
Assumption 3 implies the existence of two well-matched full-rank matrices A ∈ R n×r
and D ∈ R r×n that induce the linear operators A and D. Connected to these opera- tors are two decoupling operators which correspond to the two steps of the decoupling procedure mentioned above. In the following, we rst dene the decoupling opera- tors and show how such operators can be explicitly constructed. Next, we show that the decoupling operators rightfully bear their name, see Lemmas 2.16 and 2.17.
**Denition 2.14.** Let Assumption 3 hold. Let A − ∈ R r×n and D − ∈ R n×r be generalized inverses to A and D. We call two matrices Q ∈ R n×(n−r) and W ∈ R (n−r)×n r×(n−r) and
|a pair of decoupling matrices provided that DQ|= 0 ∈|R|
|(n−r)×r|||
|−|− n×n||
WA = 0 ∈ R (n−r)×r holds, and that the composed matrices [] [] n×nA D Q ∈ R and ∈ R (2.22) W
<u>2.3 Dissection-based Decoupling Procedure</u>
are invertible. If Q and W fulll these requirements, we call the corresponding induced linear operators
Q : L p (Ω, R n−r )→L p (Ω, R n ) and W : L p (Ω, R n )→L p (Ω, R n−r
) (2.23)
*a pair of decoupling operators for the abstract DAE* (2.19).
**Lemma 2.15.** *Let Assumption 3 hold. Then, there exists a pair of decoupling* *operators for the abstract DAE* (2.19) *as in Denition 2.14.*
**Proof.** Note that A and D both have rank r < n by Assumption 3. By the Rank- Nullity Theorem, we have dim ker D = n − r = dim ker A T where A T ∈ R n×r de- notes the transposed of A. Denote with {q₁,...,qn−r} a basis of ker D, and with {w₁,...,wn−r} a basis of ker A T. Dene matrices     | | | | Q := q₁ · · · qn−r∈R n×(n−r) and W T := w₁ · · · wn−r∈R n×(n−r). | | | |
Then, Q and W are a pair of decoupling matrices as in Denition 2.14. In fact, DQ = 0 and A T W T = 0 are evident by construction, the latter being equivalent to WA = 0. Moreover, by Lemma A.10
|−|n|− T|
|−|−||
R n = ker D ⊕ im D and R = ker A T ⊕ im(A) (2.24)
hold for generalized inverses D of D and A of A, and consequently, the composed matrices (2.22) are invertible.
The linear operators Q and W induced by Q and W are, by denition, a pair <u>of</u> decoupling operators for DAE (2.19).
**Lemma 2.16.** *Let Assumption 3 hold. Let* A − *and* D − *be generalized inverses to the* *well-matched operators* A *and* D *such that* A − *and* D − *are induced by generalized* *inverse matrices* A − *and* D − *. Let* Q *and* W *be a corresponding pair of decoupling* *operators for DAE* (2.19) *induced by a pair of decoupling matrices* Q *and* W *as in*
||1,p|n||
|---|---|---|---|
||D|||
|1,p|p r||p|
||||a|
p *Denition 2.14. Let* u ∈ W (0,T; L (Ω, R)) *be xed. Then, there are functions*
ud∈ W (0,T; L (Ω, R)) *and* u ∈ L (0,T; L p (Ω, R n−r ))
*such that* u = D − ud+ Qua(2.25)
*holds.*
<u>2 Analysis of an Abstract Semilinear DAE</u>
**Proof.** As before, we x a generalized inverse D − ∈ R n×r of D. By Denition 2.14 and Corollary 2.6, the linear operator S ∈ L(L p (Ω, R n )) induced by the composed matrix [D − Q] of (2.22) is invertible. Thus, there exists a uniquely determined u¯ := S −1 u where S has to be understood as in Denition 2.2. For almost all t ∈ [0,T], the vector-valued function u¯(t) is well-dened, and we denote with ud(t) the rst r, and with ua(t) the remaining (n − r) component functions. In other words, we dene pointwise    
|u ¯ (t)||u ¯ (t)||
|---|---|---|---|
|1|p r|r+1|p n−r|
|r||n||
.  .  ud(t) := .. ∈L (Ω, R) and ua(t) := .. ∈L (Ω, R). (2.26) u¯ (t) u¯ (t)
Then, we have for almost all x ∈ Ω
[u(t)](x) = [Su¯(t)](x) = S([u¯(t)](x)) () () [ud(t)](x) [−] [ud(t)](x) = S = D Q [ua(t)](x) [ua(t)](x)
= D − ([ud(t)](x)) + Q([ua(t)](x))
= [D − (ud(t))](x) + [Q(ua(t))](x)
= [(D − ud)(t)](x) + [(Qua)(t)](x)
= [(D − ud+ Qua)(t)](x).
|Consequently,|the decomposition (2.25) holds.||||Finally, we comment on the reg-|||
|---|---|---|---|---|---|---|---|
||d|a|||||−1|
|p|p n p d|p|r|p|p n p a|p|n−r|
||−|d −|p −|r|1,p|p|r|
|d|d|a|d|a||||
ularity of u and u. Note that by Denition 2.2, S as well as S map into L (0,T; L (Ω, R)) and therefore u¯∈L (0,T; L (Ω, R)) holds. Consequently, also
u ∈ L (0,T; L (Ω, R)) and u ∈ L (0,T; L (Ω, R))
holds. Moreover, u is even weakly dierentiable: Recall from the proof of Theo- rem 2.10 that DD = id ∈ L(L (Ω, R)), see (2.16). Thus,
u = DD u + DQu = D(D u + Qu) = Du ∈ W (0,T; L (Ω, R)). (2.27)
##### This concludes the proof.
At the beginning of this section, we described our twofold splitting technique. Al- though it may not be obvious at this point, Lemma 2.16 eectively concludes the rst part of the splitting procedure. Observe that in particular ud∈ im D holds which is consistent with the remark we made on page 19. At this point, we once more draw attention to the following issue: We introduced the variables udand ua connotatively, the subscript “d” meaning *dynamical*, and the subscript “a” meaning *algebraic*, i. e. non-dynamical. But the surjectivity of D, provided by Assumption 3 and Theorem 2.10, only ensures that udare, in fact, the dierentiated variables and
<u>2.3 Dissection-based Decoupling Procedure</u>
uaare the non-dierentiated variables in our reformulation (2.19) of the abstract DAE (2.2). This will become clearer soon. A criterion which guarantees that ud collects indeed the dynamical variables and that uaassembles the non-dynamical variables of the abstract DAE (2.2) will be given in the subsequent Section 2.4. For now, we turn to the second part of the splitting procedure and present a way to separate the equations containing derivatives from those that are derivative-free.
**Lemma 2.17.** *Let Assumption 3 hold. Let* A − *and* D − *be generalized inverses to the* *well-matched operators* A *and* D *such that* A − *and* D − *are induced by generalized* *inverse matrices* A − *and* D − *. Let* Q *and* W *be a corresponding pair of decoupling* *operators for the abstract DAE* (2.19) *induced by a pair of decoupling matrices* Q *and* W *as in Denition 2.14. Then,* (2.19) *can be dissected into the system* { u ′d
(t) + A − φ(t, (D
− ud+ Qua)(t)) = A − q(t) *f. a. a.* t ∈ [0,T]*,* (2.28a)
W φ(t, (D − ud+ Qua)(t)) = W q(t) *f. a. a.* t ∈ [0,T]*.* (2.28b)
*Equation* (2.28a) *contains the dierentiated terms, and* (2.28b) *is derivative-free.*
||−|r×n|
|− p|n|p|
||p r||
**Proof.** As before, we x a generalized inverse A ∈ R of A. Note that the cor- responding induced linear operator A : L (Ω, R)→L (Ω, R r ) fullls the relation
A − A = id ∈ L(L (Ω, R))
which follows just as (2.16) in the proof of Theorem 2.10. Multiplying DAE (2.19) by A −, we thus obtain
A − A(Du) ′
(t) + A − φ(t,u(t)) = A
− q(t) f. a. a. t ∈ [0,T]
⇐⇒ (Du) ′
(t) + A − φ(t,u(t)) = A
− q(t) f. a. a. t ∈ [0,T].
Moreover, by Lemma 2.16, we can decompose u as in (2.25) and the relation (2.27) reveals that the last equation is equivalent to
u ′d
(t) + A − φ(t, (D
− ud+ Qua)(t)) = A − q(t) f. a. a. t ∈ [0,T].
This is precisely (2.28a). To recover the complementing derivative-free equation, we apply W to DAE (2.19). The fact that WA = 0 holds by Denition 2.14 transfers directly to the corresponding induced linear operators, i. e. WA = 0, and therefore
WA(Du) ′
(t) + W φ(t,u(t)) = W q(t) f. a. a. t ∈ [0,T]
⇐⇒ W φ(t, (D − ud+ Qua)(t)) = W q(t) f. a. a. t ∈ [0,T]
holds, the last equation being (2.28b). Note how (2.28a) is actually a system of r equations which includes derivative terms only of the r weakly dierentiable com- ponent functions ud∈ W 1,p (0,T; L p (Ω, R r )). Also, (2.28b) is a system of (n − r)
<u>2 Analysis of an Abstract Semilinear DAE</u>
equations. As mentioned before, this is exactly what we expected from a dissection- based approach. We thus arrive at the dissected system (2.28) which notably is not bigger in size than the original DAE (2.19). This concludes the second step of the splitting procedure.
To summarize, we reformulated our initial abstract DAE (2.2) into the abstract DAE with properly stated leading term (2.19). We then used the decoupling operators of Denition 2.14 to decouple the solution variable u into two parts, udand ua. We derived system (2.28) which consists of an equation containing derivatives and a complementing derivative-free equation.
It remains to show that the abstract DAE (2.19) and the dissected system (2.28) are equivalent in the sense that given a solution to one of the two systems, we can derive a solution to the other one. It is already clear that if u is a solution to (2.19), then the pair (ud,ua) given by (2.26) solves the decoupled system (2.28). At rst sight, it might, however, not be obvious that the converse also holds true. The equivalence of both systems is ascertained by virtue of the following two theorems.
**Theorem 2.18.** *Let Assumptions 1 and 3 hold. Assume that the function* u ∈ 1,p p n W D (0,T; L (Ω, R)) *solves the properly stated DAE*
A(Du) ′
(t) + φ(t,u(t)) = q(t) *f. a. a.* t ∈ [0,T]*.* (2.19)
##### Then, there are functions
||p|n−r|
||a||
|− −||d a|
ud∈ W 1,p (0,T; L p (Ω, R r )) *and* u ∈ L (0,T; L p (Ω, R))
*and matrix-induced linear operators* A*,* D*,* Q*, and* W *such that* (u,u) *solves* *the dissected system* { u ′d
(t) + A − φ(t, (D
− ud+ Qua)(t)) = A − q(t) *f. a. a.* t ∈ [0,T], − (2.28) W φ(t, (D ud+ Qua)(t)) = W q(t) *f. a. a.* t ∈ [0,T]*.*
**Proof.** This is a direct consequence of the discussion of Sections 2.2 and 2.3 above, and in particular Lemma 2.17.
**Theorem 2.19.** *Let Assumptions 1 and 3 hold, and let matrix-induced linear oper-* *ators* A − *,* D − *,* Q *and* W *be given such that*
|− −|||
||− −|p r|
*i)* A *and* D *are generalized inverses of* A *and* D *respectively that fulll*
DD = A A = id ∈ L(L (Ω, R));
*ii)* Q *and* W *are decoupling operators in the sense of Denition 2.14.*
<u>2.3 Dissection-based Decoupling Procedure</u>
*Instead of considering the properly stated DAE* (2.19)*, consider the system* { u ′1
(t) + A − φ(t, (D
− u₁ + Qu₂)(t)) = A − q(t) *f. a. a.* t ∈ [0,T], − (2.29) W φ(t, (D u₁ + Qu₂)(t)) = W q(t) *f. a. a.* t ∈ [0,T]*,*
*and assume that it admits a solution* (u₁,u₂) *with*
u₁ ∈ W 1,p (0,T; L p (Ω, R r )) *and* u₂ ∈ L p (0,T; L p (Ω, R n−r )).
##### Then, the function
− 1,p p n u := D u₁ + Qu₂ ∈ W D (0,T; L (Ω, R))
##### is a solution to DAE (2.19).
**Proof.** First, note that the denition of u makes sense since both D − and Q, under- stood as in Denition 2.2, map to L p (0,T; L p (Ω, R n )) by Denitions 2.4 and 2.14. Moreover, by assumption
Du = DD − u₁ + DQu₂ = u₁
holds, and thus, u has the desired regularity since u₁ ∈ W 1,p (0,T; L p (Ω, R r )). This allows to rewrite system (2.29) as { (Du) ′
(t) + A − φ(t,u(t)) = A
− q(t) f. a. a. t ∈ [0,T], W φ(t,u(t)) = W q(t) f. a. a. t ∈ [0,T].
By assumption, A − A = id holds as well as WA = 0, thus the last system is equivalent to { A − A(Du) ′
(t) + A − φ(t,u(t)) = A
− q(t) f. a. a. t ∈ [0,T], WA(Du) ′
(t) + W φ(t,u(t)) = W q(t) f. a. a. t ∈ [0,T].
The rst equation holds in L p (Ω, R r ), the second one in L p (Ω, R n−r ). Consequently, for almost all x ∈ Ω and t ∈ [0,T], we have {[] [] A − (A(Du) ′
(t) + φ(t,u(t))) (x) = A
− q(t) (x), [ ′] [] W (A(Du) (t) + φ(t,u(t))) (x) = W q(t) (x).
By denition of matrix-induced linear operators however, this is equivalent to [ −] ( ) [ −] A′] A [A(Du) (t) + φ(t,u(t)) (x) = q(t)(x). W W
<u>2 Analysis of an Abstract Semilinear DAE</u>
[−] But the composed matrixA W is invertible by assumption on W. Thus, the last equation holds if and only if u as dened above fullls
′] [A(Du) (t) + φ(t,u(t)) (x) = q(t)(x)
for almost all t ∈ [0,T] and almost everywhere in Ω. In other words, u is indeed <u>a</u> solution to DAE (2.19).
It is worth mentioning that all what we did so far is essentially to rewrite the initial abstract DAE (2.2) into the system (2.28). The last two theorems show that this is justied in the sense that both systems are equivalent. However, we still need to state a reason why it would be sensible to consider (2.28) instead of (2.2). The rationale for this is given in the following section.
##### 2.4 Existence Theory
In this section, we nally deal with the questions that have remained open so far, namely what we mean by consistent initial values, why udand uaindeed correspond to the dynamical and non-dynamical part of our solution, and what assumptions are sucient to guarantee that the abstract DAE (2.19) has got an index-1 character. Moreover, we state with Theorem 2.22 an existence and uniqueness result for the decoupled system (2.28) and consequently also for abstract DAEs (2.19) and (2.2).
Let us begin by rst discussing the index-1 character of our abstract DAE. The dening feature of a DAE with an inherent index-1 structure is that although the inherent dynamics are subject to algebraic constraints, we can solve the system with- out dierentiating any right-hand side functions. Ergo, our introductory example on page 6 is *not* an index-1 DAE. However, in order to solve the DAE, we still need to solve the constraining equations for the non-dynamical variables. In other words, we need to be able to express the non-dynamical variables as a function of the dy- namical ones. For DAEs, a common way to do this is by using the Implicit Function Theorem. But this requires a certain dierentiability which is often too strong an assumption in contexts where abstract DAEs appear. Instead, the operators in ab- stract DAEs are often supposed to satisfy certain strong monotonicity assumptions, see [9, 50, 86, 119], or comparably certain ellipticity assumptions, see [10, 128]. The constraining equations are then usually solved by means of the Theorem by Browder and Minty C.9, Zarantonello’s Theorem C.10, or variations thereof.
In the recent article [50], the authors developed a novel technique to analyze a nonlinear DAE with an elliptic PDE constraint; see [50, Theorem 2]. Due to this technique, they were able to exploit the monotonicity properties of the nonlinear operators for a rigorous error analysis of a specic discretization of the system. With Theorem 2.20 we present a generalization of this technique under considerably
<u>2.4 Existence Theory</u>
lower assumptions. Applied to our abstract DAE (2.2), this allows to reduce the assumptions on the nonlinear function φ of (2.2), yet we are still able to solve the derivative-free equations for the non-dierentiated variables. Since we may do so without any additional dierentiations, the assumptions on φ can be interpreted as an index-1-like criterion, and the dierentiated and non-dierentiated components udand uaof (2.28) correspond indeed to the dynamical and algebraic variables of the abstract DAE (2.2). We summarize these requirement in Assumption 4 below. But rst, we present the technique mentioned above. It is an existence result for a specic type of operator equations, based on the well-known Theorem by Browder and Minty C.9, and the assumptions stated here are related to the assumptions of Zarantonello’s Theorem C.10.
**Theorem 2.20.** *Let* T > 0 *be given, let* X *and* Y *be Banach spaces, and assume* Y *to be separable and reexive. Let* F : [0,T] × X × Y → Y ′ *be a continuous operator.* *Assume that* F *is locally Lipschitz continuous with respect to the second variable,*
*i. e. for all* t₀ ∈ [0,T]*,* x₀ ∈ X *and* y₀ ∈ Y*, there are positive numbers* c₁,c₂,c₃ > 0 *and a constant* L(c₁,c₂,c₃)≥0 *such that the estimation*
‖F (t,x₁,y) − F (t,x₂,y)‖ Y′ ≤ L(c₁,c₂,c₃)‖x₁ − x₂‖X
*holds for all* t ∈ [0,T] *with* |t − t₀| ≤ c₁*, for all* x₁,x₂ ∈ X *with* ‖x₁ − x₀‖X≤ c₂ *and* ‖x₂ − x₀‖X≤ c₂*, and for all* y ∈ Y *with* ‖y − y₀‖ ≤ c₃*. Assume moreover that* F *is* *strongly monotone with respect to the third variable, i. e. there is a constant* µ > 0 *such that* 〈 〉 2 F (t,x,y₁) − F (t,x,y₂),y₁ − y₂ Y ≥ µ‖y₁ − y₂‖Y
*holds for all* y₁,y₂ ∈ Y *and uniformly for* t ∈ [0,T] *and* x ∈ X*.*
*Then, for any xed right-hand side* b ∈ Y ′ *, there is a uniquely dened continuous* *function* g : [0,T] × X → Y *such that for all* t ∈ [0,T]*, and for all* x ∈ X *and* y ∈ Y*,* *the equivalence* y = g(t,x) ⇐⇒ F (t,x,y) = b
*holds. Additionally,* g *is locally Lipschitz continuous with respect to the second* *variable in the sense of Denition C.1.*
**Proof.** Fix t ∈ [0,T] and x ∈ X, and introduce an auxiliary operator A (t,x) : Y → Y ′
through A (t,x)
(y) := F (t,x,y).
This operator is continuous and strongly monotone; it inherits these properties di- rectly from F. The Theorem by Browder and Minty C.9 ensures that the operator equation A (t,x)
(y) = b (2.30)
<u>2 Analysis of an Abstract Semilinear DAE</u>
(t,x). This allows to dene, in a unique
|admits a unique solution which we denote by y||
|---|---|
|way, a mapping g : [0,T] × X → Y|that assigns to each pair (t,x) ∈ [0,T] × X the|
|corresponding unique solution y|of Equation (2.30). In other words, we set|
(t,x)
g(t,x) := y (t,x)
for all (t,x) ∈ [0,T] × X. Note that by denition of g, the equation
F (t,x,g(t,x)) = A (t,x) (g(t,x)) = b (2.31)
holds for all (t,x) ∈ [0,T] × X.
In order to show the continuity of g, let a convergent sequence (tk,xk) ∈ [0,T] × X with limit point (t∗,x∗) ∈ [0,T] × X be given. The strong monotonicity of F with respect to the third variable gives rise to the estimation ∥ ∥ µ∥g(tk,xk) − g(t∗,x∗)∥ Y ≤ ‖F (tk,xk,g(tk,xk)) − F (tk,xk,g(t∗,x∗))‖ Y′ ≤ ‖F (tk,xk,g(tk,xk)) − F (t∗,x∗,g(t∗,x∗))‖ Y′ + ‖F (t∗,x∗,g(t∗,x∗)) − F (tk,xk,g(t∗,x∗))‖ Y′.
The rst addend vanishes for all k by (2.31), the second one tends to 0 for k → ∞ due to the continuity of F. Thus, g is continuous. Similarly, we show using (2.31) that g is locally Lipschitz with respect to the second variable. To this end, let t₀ ∈ [0,T] and x₀ ∈ X be arbitrarily xed, and set y₀ := g(t,x₂) ∈ Y. By assumption on F, there are positive numbers c₁,c₂,c₃ > 0 such that ∥ ∥ µ‖g(t,x₁) − g(t,x₂)‖Y≤ ∥F (t,x₁,g(t,x₁)) − F (t,x₁,g(t,x₂))∥ Y′ ∥ ∥ = ∥b − F (t,x₁,g(t,x₂))∥ Y′ ∥ ∥ = ∥F (t,x₂,g(t,x₂)) − F (t,x₁,g(t,x₂))∥ Y′ ≤ L(c₁,c₂,c₃)‖x₂ − x₁‖X
holds for all t ∈ [0,T] with |t − t₀| ≤ c₁, and for all x₁,x₂ ∈ X with ‖x₁ − x₀‖X≤ c₂ and ‖x₂ − x₀‖X≤ c₂. Thus, g is locally Lipschitz continuous with respect to the second variable in the sense of Denition C.1.
**Remark.** The assumption of the separability of Y can be relaxed; see the remark on page 121. The assumption of strong monotonicity on F could be reduced to uniform monotonicity but this does not change anything essential. Both types of monotonic- ity provide an estimation of the form (C.6). In addition, strong monotonicity implies the Lipschitz continuity of the inverse operator (A (t,x) ) −1 whereas uniform mono- tonicity only implies continuity of this inverse operator but neither comes into play here as we do not perturb the right-hand side.
<u>2.4 Existence Theory</u>
**Assumption 4.** Let Assumptions 1 and 3 hold. Let A − and D − be generalized inverses to the well-matched operators A and D such that A − and D − are induced by generalized inverse matrices A − and D −. Let Q and W be a corresponding pair of decoupling operators for the abstract DAE (2.19) as in Denition 2.14. We need the following requirements to hold.
i) Let p = 2. This assumption is discussed in the subsequent remark. ii) The right-hand side function of the abstract DAE (2.19) fullls q ∈ L²(0,T; L²(Ω, R
n )) with W q ∈ C([0,T]; L²(Ω, R n−r )).
iii) The nonlinear function φ : [0,T] × L²(Ω, R n )→L²(Ω, R n ) is continuous.
##### iv) The operator
Φ : [0,T] × L²(Ω, R r )×L²(Ω, R n−r )→L²(Ω, R n ),
which, for ud∈ L²(Ω, R r ) and ua∈ L²(Ω, R n−r ), is dened through
Φ(t,ud,ua) := φ(t, D − ud+ Qua),
is locally Lipschitz continuous with respect to the second variable.
In view of Chapter 4 we point out that Φ is not a Nemytskii operator.
v) The composite operator
W Φ : [0,T] × L²(Ω, R r )×L²(Ω, R n−r )→L²(Ω, R n−r )
is strongly monotone with respect to third variable.
**Remark.** Above assumptions iii), iv), and v) together form eectively our index-1- like criterion. Since for the discussion of this chapter we always have strong solutions in mind, i. e. solution functions which have got the same spatial regularity as their time derivatives, we essentially need the space Y of Theorem 2.20 to coincide with its dual. This is the case for Hilbert spaces, and it is why we restrict ourselves to p = 2 in Assumption 4. For the systems analyzed in the course of the thesis, this is not a severe restriction as the discussion of the next chapters, in particular of Chapter 4, will also be restricted to the case p = 2. Possible generalizations are discussed in Section 2.5.
**Theorem 2.21.** *Let Assumptions 1, 3, and 4 hold. Then, there exists a unique* *continuous function* g : [0,T] × L²(Ω, R r )→L²(Ω, R n−r ) *such that*
##### W Φ(t,ud,ua) = W q(t)
<u>2 Analysis of an Abstract Semilinear DAE</u>
*holds for* t ∈ [0,T]*,* ud∈ L²(Ω, R r )*, and* ua∈ L²(Ω, R n−r ) *if and only if*
##### ua= g(t,ud) (2.32)
*holds. Moreover,* g *is locally Lipschitz continuous with respect to the second variable.*
**Proof.** In correspondence to Theorem 2.20, we introduce an operator
F : [0,T] × L²(Ω, R r )×L²(Ω, R n−r )→L²(Ω, R n−r ), through F (t,ud,ua) := W Φ(t,ud,ua) − W q(t),
This operator is continuous since φ and W q are continuous. It is locally Lipschitz continuous with respect to the second variable since Φ has this property and W is bounded by the spectral norm of its inducing matrix. Also, F is strongly monotone with respect to the third variable, which follows directly from the assumption on W Φ. By Theorem 2.20, there exists a unique continuous function g : [0,T] × L²(Ω, R r ) → L²(Ω, R n−r ) such that F (t,ud,ua) = 0 is fullled if and only if ua= g(t,ud) holds. Moreover, g is locally Lipschitz continuous with respect to its second variable.
**Remark.** Note that Assumption 4 species conclusively the choice of all of the in- volved matrix-induced linear operators. This entails the uniqueness of g. However, choosing dierent operators in the rst place may lead to a dierent decoupled sys- tem (2.28), and consequently to a dierent given function g connecting dynamical and non-dynamical components of the solution.
We used the rather general Theorem 2.20 to prove that the requirements stated in Assumption 4 are sucient to guarantee that DAE (2.2) has an internal index-1- like structure. Up to this point, udand uadescribed the dierentiated and non- dierentiated components of a solution. The relation (2.32) nally shows that ud are indeed the dynamical and uathe algebraic components; uacan be written as a function of udwithout additional dierentiations of right-hand side functions. We can use (2.32) to rewrite (2.28a) in terms of udonly, namely as
u ′d
(t) + A − φ(t, D
− ud(t) + Qg(t,ud(t))) = A − q(t). f. a. a. t ∈ [0,T] (2.33)
This is the inherent ODE of our abstract DAE (2.2) which describes the inherent dynamics. It is now also clear how to prescribe initial values. Since the algebraic variables are determined conclusively from the dynamical variables by (2.32), we can prescribe initial values for udonly. Also u(0) ∈ im D needs to hold. From these, the initial values of uaare to be inferred.
Observe that the dissection-based decoupling approach we chose in Section 2.3 only works due to the Assumption 4 and Theorem 2.20. This approach applied to an
<u>2.4 Existence Theory</u>
abstract DAE of the form (2.2) always leads to a system of the form (2.28) but as stated before, this has to be seen as a mere reformulation. It is Assumption 4 and Theorem 2.20 which allow to solve the derivative-free equations in a way that allows uato be written as a function of ud.
We conclude this section by presenting an existence and uniqueness result for solu- tions to an initial value problem based on the dissected system (2.28). Note that under our current assumptions, classical results from ODE theory do not apply, at least not directly. Although there are generalized versions of Peano’s Theorem and the Theorem by Picard and Lindelöf, both require already in the nite-dimensional case that all appearing functions are at least continuous with respect to time. In order to transfer Peano’s Theorem to the innite-dimensional case, the continuity assumption needs to be replaced by a stronger compactness criterion since the proof is based on Schauder’s xed-point theorem; see for instance [39, pp. 190 sqq.]. This holds true for the more general existence result by Carathéodory as well; see for instance [60, pp. 28 sq.]. This issue also appears even when we try to use results from semigroup theory which is explicitly tailored for Banach space valued ODEs. See for instance Theorem 1.4 in the textbook by Pazy [95, pp. 185 sqq.].
So far, we only demanded φ to be continuous but not the right-hand side A −
q. Note
that Assumption 4 already contains a local Lipschitz condition. Thus, we aim to provide an existence and uniqueness result based on the Generalized Picard-Lindelöf Theorem C.3 whilst trying to deviate from our previous assumptions as little as possible. In particular, the issue of the discontinuity of A − q can be overcome by a specic trick we took from [108, pp. 197 sq.].
**Assumption 5.** Let Assumptions 1, 3, and 4 hold. In addition, we need the following requirements to hold.
i) The nonlinear function φ : [0,T] × L²(Ω, R
n )→L²(Ω, R n ) is assumed to be locally Lipschitz continuous with respect to the second variable in the sense of Denition C.1.
ii) For simplicity, we also assume φ to be bounded. Compare this to the assumption on f in the Generalized Picard-Lindelöf Theorem C.3, that is the existence of an a priori estimate. Compare also to the requirement of uniform Lipschitz continuity for the version of the generalized Picard-Lindelöf Theorem stated in [39, pp. 169 sqq.].
**Remark.** The assumption on φ to be locally Lipschitz continuous implies the local Lipschitz continuity of the operator Φ as required by Assumption 4.
**Theorem 2.22.** *Let Assumptions 1, 3, 4, and 5 hold. Consider the initial value*
<u>2 Analysis of an Abstract Semilinear DAE</u>
*problem*
 ′ − − −  ud
(t) + A φ(t, (D ud+ Qua)(t)) = A q(t) *f. a. a.* t ∈ [0,T], (2.34a)
−
||W φ(t, (D|u + Qu )(t)) = W q(t)||(2.34b)|
|---|---|---|---|---|
|||d|a||
||r||d|d a|
d a*f. a. a.* t ∈ [0,T],   u (0) = u₀ (2.34c)
*for given* u₀ ∈ L²(Ω, R) = im D*. Then, this system admits a unique solution* (u,u) *with*
ud∈ H¹(0,T; L²(Ω, R r )) *and* ua∈ L²(0,T; L²(Ω, R n−r )).
**Proof.** Instead of system (2.34), we consider the system  ()  u ′d
(t) + A − φ t, D
− ud(t) + Qg(t,ud(t)) = A − q(t) f. a. a. t ∈ [0,T],
f. a. a. t ∈ [0,T],
||u (t) = g(t,u|(t))|
||a|d|
||d||
  u (0) = u₀,
(2.35a) (2.35b) (2.35c) where g is the unique implicit function provided by Theorem 2.21. As a matter of fact, (2.34b) and (2.35b) are equivalent. It is not relevant that the second variable in g now also depends on t; observe also that the continuity of g does not imply the continuity of the mapping t 7→ g(t,ud(t)).
In order to prove existence and uniqueness of a solution to (2.35) by means of the Generalized Picard-Lindelöf Theorem C.3, we rst show that the nonlinear term
A − φ(t, D − ud(t) + Qg(t,ud(t)))
fullls a local Lipschitz condition. Afterwards, we discuss how to treat the possibly discontinuous right-hand side function A −
q.
We begin and dene an auxiliary function h : [0,T] × L²(Ω, R r )→L²(Ω, R n ) through
h(t,u˜) := D − u˜ + Qg(t,u˜) for t ∈ [0,T] and u˜∈L²(Ω, R r ).
This function h is locally Lipschitz continuous with respect to the second variable in the sense of Denition C.1. In fact, x t₀ ∈ [0,T] and u˜0∈ L²(Ω, R r ) arbitrarily. By assumption on g, there are positive numbers c₁,c₂ > 0 and a constant Lg= Lg(c₁,c₂)≥0 such that for all t ∈ [0,T] with |t − t₀| ≤ c₁ and all u˜1,u˜2∈ B(u˜0,c₂), the estimation
##### ‖g(t,u˜1) − g(t,u˜2)‖L2(Ω,Rn−r)≤ Lg‖u˜1− u˜2‖L2(Ω,Rr)
<u>2.4 Existence Theory</u>
holds. For h, we thus have by linearity of D − and Q
‖h(t,u˜1) − h(t,u˜2)‖L2(Ω,Rn)= ‖D − u˜1+ Qg(t,u˜1) − D − u˜2− Qg(t,u˜2)‖L2(Ω,Rn)
≤ ‖D − ‖‖u˜1− u˜2‖L2(Ω,Rr) + ‖Q‖‖g(t,u˜1) − g(t,u˜2)‖L2(Ω,Rn−r) ( − ) ≤ ‖D ‖ + ‖Q‖Lg‖u˜1− u˜2‖L2(Ω,Rr)
for all t ∈ [0,T] with |t − t₀| ≤ c₁ and u˜1,u˜2∈ B(u˜0,c₂). We recall moreover from (2.5) that the norms of D − and Q are bounded by the spectral norms of their respective inducing matrices. This shows that h is locally Lipschitz continuous.
Next, introduce the function φ˜: [0,T] × L²(Ω, R r )→L²(Ω, R r ) through
φ˜(t,u˜) := A − φ(t, D − u˜ + Qg(t,u˜)) = A − φ(t,h(t,u˜)). (2.36)
The composition φ ◦ h : [0,T] × L²(Ω, R r )→L²(Ω, R n ) dened as in (2.39) by
##### (φ ◦ h)(t,u˜) := φ(t,h(t,u˜))
is also locally Lipschitz continuous; see the auxiliary Lemma 2.23 subsequent to this proof. The leading A − in the denition of φ˜ in (2.36) only changes the Lipschitz constant but not the local Lipschitz continuity itself. Hence, φ˜ is also locally Lipschitz continuous with respect to the second variable.
Using φ˜, we rewrite (2.35a), and together with the initial condition (2.35c), we obtain the initial value problem { u ′d
(t) + φ˜(t,ud(t)) = A
− q(t) f. a. a. t ∈ [0,T], (2.37a) ud(0) = u₀. (2.37b)
Still, we cannot apply the Generalized Picard-Lindelöf Theorem C.3 to this system due to missing continuity on the right-hand side. To overcome this issue, we dene an abstract function q˜: [0,T] → L²(Ω, R r ) through ∫t q˜(t) := A − q(s) ds for t ∈ [0,T]. 0
By Lemma B.19, the function q˜ is absolutely continuous, even classically dieren- tiable almost everywhere, and clearly q˜ ∈ H¹(0,T; L²(Ω, R r )) with q˜ ′ = A −
q. We
consider the auxiliary initial value problem { () υ ′
(t) + φ˜ t,υ(t) + q˜(t) = 0 for t ∈ [0,T],
(2.38) υ(0) = u₀.
The function t 7→ φ˜(t,υ + q˜(t)) is continuous, and the function υ 7→ φ˜(t,υ + q˜(t)) is, again, locally Lipschitz continuous; the translation by q˜ in the second argu- ment does not change this. Recall that by Assumption 5, φ and consequently φ˜
<u>2 Analysis of an Abstract Semilinear DAE</u>
is bounded. Thus, by the Generalized Picard-Lindelöf Theorem C.3, the initial value problem (2.38) admits a unique continuously dierentiable solution υ : [0,T] → L²(Ω, R r ).
We now double back and step by step return to system (2.34). Having found a unique solution υ to (2.38), we set
ud:= υ + q˜ ∈ H¹(0,T; L²(Ω, R r )).
This function solves system (2.37). In fact, the initial condition (2.37b) holds since q˜(0) = 0 by denition. Moreover, we have for almost all t ∈ [0,T]
|′d ′|′|−|
|||d|
u (t) = υ (t) + q˜ (t) = −φ˜(t,υ(t) + q˜(t)) + A − q(t) = −φ˜(t,u (t)) + A q(t),
which is equivalent to (2.37a). But (2.37a) is equivalent to (2.35a), and therefore the dynamical part of our solution to (2.35) is uniquely determined. The relation (2.35b) now denes uniquely the algebraic components ua. In summary, we found a unique pair (ud,ua) which solves (2.35), and consequently (2.34).
**Remark.** From the solution (ud,ua) provided by Theorem 2.22 we may, as before, uniquely reconstruct a function u ∈ H D 1 (0,T; L²(Ω, R n )) using the relation (2.25). This function u solves our properly stated abstract DAE (2.19).
We conclude this section by providing the promised auxiliary result which shows that a specic composition of two locally Lipschitz continuous functions is still locally Lipschitz continuous.
**Lemma 2.23.** *Let* X*,* Y*, and* Z *be real Banach spaces, and let* [0,T] ⊂ R *be a given* *xed time interval with* T > 0*. Let* f : [0,T] × X → Y *and* g : [0,T] × Y → Z *be two* *continuous mappings which are locally Lipschitz continuous with respect to their* *respective second variables, see Denition C.1. Then, the composition* g ◦ f : [0,T] × X→Z *given by*
(g ◦ f)(t,x) := g(t,f (t,x)) *for* t ∈ [0,T] *and* x ∈ X (2.39)
*is locally Lipschitz continuous with respect to its second variable, i. e. for all* t₀ ∈ [0,T] *and* x₀ ∈ X *there are positive numbers* c₁,c₂ > 0 *and a constant* L(c₁,c₂)≥0 *such that* ‖g(t,f (t,x₁)) − g(t,f (t,x₂))‖Z≤ L(c₁,c₂)‖x₁ − x₂‖X
*holds for all* t ∈ [0,T] *with* |t − t₀| ≤ c₁*, as well as for all* x₁,x₂ ∈ B(x₀,c₂)⊂X*.*
<u>2.4 Existence Theory</u>
**Proof.** Let t₀ ∈ [0,T] and x₀ ∈ X be arbitrarily xed. By assumption on g, there are positive numbers c)≥0 such that
||,c > 0 and a constant L||= L|(c ,c||
|---|---|---|---|---|---|
||g1 g2|Z g1|g g f 1 f 2|g g1 g2 Y|g2 f|
|f f 1 f 2 f 2||Y|f|f 1 X||
‖g(t,y₁) − g(t,y₂)‖ ≤ L ‖y₁ − y₂‖ (2.40)
is fullled for all t ∈ [0,T] with |t − t₀| ≤ c, and all y₁,y₂ ∈ B(f (t₀,x₀),c)⊂Y.
Similarly for f, there are positive numbers c,c > 0 and a constant L = <u>L</u> (c,c) such that for all t ∈ [0,T] with |t − t₀| ≤ c and for all x₁,x₂ ∈ B(x₀,c), we have
‖f (t,x₁) − f (t,x₂)‖ ≤ L ‖x₁ − x₂‖. (2.41)
Since f and g are only locally Lipschitz continuous, we need to pay attention to a certain technicality. Essentially, it is not clear that f maps the ball around (t₀,x₀) where f is Lipschitz continuous into the ball around f (t₀,x₀) where g is Lipschitz continuous. Showing this is the principle task in proving Lemma 2.23.
By continuity of f, the mapping t 7→ ‖f (t,x₀)‖Yis continuous. In particular, it is continuous in t₀. Thus, for ε := <u>1</u> 2 c g2, there is a δ > 0 such that for t ∈ [0,T] we have
|t − t₀| ≤ δ =⇒ ‖f (t,x₀) − f (t₀,x₀)‖Y≤ ε.
Set c₁ := min{cf 1,cg1,δ} > 0, and choose 0 < c₂ ≤ min{cf 2,cg2} suciently small such that Lfc₂ ≤ 2 <u>1</u> c g2is fullled. Then, for all t ∈ [0,T] with |t − t₀| ≤ c₁ and for all x ∈ B(x₀,c₂), we have
‖f (t,x) − f (t₀,x₀)‖Y≤ ‖f (t,x) − f (t,x₀)‖Y+ ‖f (t,x₀) − f (t₀,x₀)‖Y <u>1 1</u> (2.42) ≤ Lf‖x − x₀‖X+ ε ≤ Lfc₂ + ε ≤ cg2+ cg2= cg2. 2 2
Since c₁ ≤ cg1by denition, this last estimation shows that there is a suciently small ball around (t₀,x₀) which is mapped under f into B(f (t₀,x₀),cg2), the latter being the set where g is Lipschitz continuous and (2.40) holds.
After these preparations, we may nally show that the composition g ◦ f as given above is also locally Lipschitz continuous. To this end, we x arbitrary t ∈ [0,T] with |t − t₀| ≤ c₁ and arbitrary x₁,x₂ ∈ B(x₀,c₂). Then,
‖(g ◦ f)(t,x₁) − (g ◦ f)(t,x₂)‖Z= ‖g(t,f (t,x₁)) − g(t,f (t,x₂))‖Z ≤ Lg‖f (t,x₁) − f (t,x₂)‖Y ≤ LgLf‖x₁ − x₂‖X
since estimation (2.42) holds for both x₁ and x₂, and B(x₀,c₂) ⊂ B(x₀,cf 2). This concludes the proof.
<u>2 Analysis of an Abstract Semilinear DAE</u>
##### 2.5 Summary and Discussion
In this chapter, we discussed the semilinear DAE
(E u) ′
(t) + φ(t,u(t)) = q(t) for 0 ≤ t ≤ T. (2.2)
Motivated by the observation that in many elds of application, for instance electrical circuits or ow networks, the leading operator E inherently describes some sort of graph structure, we introduced in Section 2.1 the notion of matrix-induced linear operators. They are mappings between Banach spaces and thus innite-dimensional objects but they behave like nite-dimensional matrices, and so may mediate between these two worlds. In order to discuss and successfully decouple abstract DAEs, i. e. DAEs in an innite-dimensional setting, it is often necessary to require that the involved operators split the underlying function space in a certain sense, for instance to assume that the null space of these operators is complemented. See for instance [86, p. 58]. A very similar assumption is necessary to guarantee the existence of generalized inverses of linear operators between Banach spaces, see [91, pp. 827 sq.]. Matrix-induced linear operators directly have such a space splitting property, they naturally appear in many applications, and we believe that they are potentially very useful in the analysis of abstract DAEs.
In Section 2.2, we provided an appropriate functional analytical framework to un- derstand the abstract DAE (2.2). We showed that a matrix-induced linear operator E can always be properly factorized, and we introduced suitable solution spaces following the work in [85].
Using these specic operators, we were able to decouple the Banach space valued DAE (2.2) by using an approach which is based on the dissection concept introduced by Jansen [64]. However, there are two major dierences to the DAEs analyzed in [64]. First, (2.2) is formulated in an innite-dimensional setting and not a nite- dimensional one. This challenge was met by using matrix-induced linear operators, and we discussed the rst part of the decoupling procedure in Section 2.3. The second major dierence is that the DAEs discussed in [64] have exclusively classical continuously dierentiable solution functions. In view of the coupled system analyzed in Chapter 4, we aimed at nding not classical but strong solutions instead, that is solutions which are continuous in time but in general not dierentiable. For this reason, we could not rely on the Implicit Function Theorem which is often used to nd the inherent ODE, see for instance [64, 65, 72]. Rather, we used a monotonicity assumption and developed an index-1-like characterization based on the novel theoretical existence result for operator equations stated in Section 2.4. This characterization has the advantage that it does not require the entire nonlinear function φ of the DAE to meet the monotonicity assumption. Only a certain image of φ, namely W φ needs to be strongly monotone, and further, it does not need to be strongly monotone on all of its domain but only on certain ane subspaces.
<u>2.5 Summary and Discussion</u>
Finally, we were able to provide an existence and uniqueness result for the decoupled DAE with discontinuous right-hand side q under fairly mild assumptions. Note that this is not trivial. In fact, typical existence results for ODEs in nite-dimensional settings are based on Schauder’s xed-point theorem, for instance Peano’s theorem or Carathéodory’s theorem. Consequently, they require the nonlinear function φ to be completely continuous or compact to be applicable also in an innite-dimensional setting. The same holds true for existence results for semilinear initial value problems based on the semigroup approach, although, this would allow to include Banach space valued operators representing spatial dierential operators. This diculty was omitted here. For more information regarding the semigroup approach applied to nonlinear problems, we refer to [95, Chapter 6].
There are many possible points where we could generalize results, discuss related concepts, relax certain assumptions. We only discuss the most important.
**More general Matrix-induced Linear Operators** For this thesis, we introduced matrix-induced linear operators with strong solutions in mind, and we chose a nota- tion comparable to the one in [85]. However, the concept of matrix-induced linear operators can naturally be transferred to work between more general Bochner spaces; consider for instance
E : L p (0,T; X) n → L p (0,T; X ′ ) m.
With this notion and the more exible notation, the decoupling procedure based on Theorem 2.20 could work also in cases other than p = 2. In addition, it would permit to analyze DAEs with respect to weaker solution concepts.
**More specic Matrix-induced Linear Operators** Besides generalizing the concept of matrix-induced linear operators to more general Bochner spaces, we could also go a step in the opposite direction. Observe that matrices representing graphs, in particular so-called Laplacian matrices, possess a lot of structure which we did not yet exploit. If a DAE arises from a eld of application where network or graph structures are present, regularly also Laplacian matrices appear, and we might gain more insight into the composition of the DAE and the topology of its underlying graph by exploiting the properties of such graph describing matrices. See for instance [94]. For more information on graphs and their describing matrices, we refer to the textbook by Molitierno [88].
**The Concept of Well-matched Factors** The concept of well-matched operators can be extended to general linear operators. Let U, V, and W be Banach spaces, and let an operator E ∈ L(U,W) be given. Two operators A ∈ L(V,W) and D ∈ L(U,V) are well-matched factors of E if E = AD holds, A is injective, and D is surjective. This
<u>2 Analysis of an Abstract Semilinear DAE</u>
implies that im D is closed and that the topological transversality condition (2.15) holds.
**Linear Operators induced by Matrix-valued Functions** The second natural con- tinuation is the extension to linear operators induced by matrix-valued functions, thus to operators
E : [0,T] × L p (0,T; X) n → L q (0,T; Y) m,
such that E (t) is a matrix-induced linear operator for (almost all) t ∈ [0,T]. This also includes systems of PDEs. Consider for instance a coupled system of elliptic and parabolic PDEs with time depending and in general discontinuous coecient functions. Such a system can directly be written as a semi-explicit abstract DAE. However, extending our results to DAEs with such operators is quite involved. We only touch upon a couple of possible diculties. First and most obvious, E (t)u ′
(t) 6=
(E (·)u(·)) ′
(t) for linear operators induced by matrix-valued functions. Thus, we
require a certain dierentiability of E if we do not want all of u but only E u to be dierentiable in a certain sense. At least, we can expect E to be continuous then. However, it is known that even in the nite-dimensional case, the continuity of a matrix-valued function E is not sucient to guarantee the continuity of a generalized inverse. In fact, the continuity of its Moore-Penrose inverse is equivalent to a constant rank condition; in other words, rank E(t) needs to be constant in time. See [26, pp. 225 sq.]. In view of ow networks, this means that the topology of the network or graph must not change. This is a restriction for applications since it may well happen in reality that valves open or close and the network topology changes in time. To the best of our knowledge, it is unclear how to tackle such problems. Even under the assumption on the linear operator E that something analog to the constant rank assumption holds, if E varies with time, its null space might also vary with time. The results for DAEs with properly stated leading term and time-varying coecients that are known so far always assume that either the null space is a C¹- subspace, which means, its basis functions are continuously dierentiable, or that E itself is continuously dierentiable. See [72, 85]. In view of coecient functions for PDEs, these are unusual strong assumptions.
**Alternatives to Strong Monotonicity** The goal of many DAE decoupling proce- dures is to nd a way to write the algebraic part of the solution in terms of the dynamical part. For DAEs, this is often done by means of the Implicit Function Theorem, and lately, in particular for abstract DAEs, this has been replaced by ap- plications of the Theorem of Browder and Minty; see [50, 64, 65, 86] amongst others. However, the fact that we assume strong monotonicity of our operator without ex- ploiting the resulting existence of a Lipschitz continuous inverse operator indicates that this assumption is perhaps too strong. We already indicated that uniform mono- tonicity might be sucient. Besides, it would be interesting to see if for instance
<u>2.5 Summary and Discussion</u>
the concept of pseudomonotonicity could be transferred to abstract DAE analysis, in particular to abstract DAEs involving spatial dierential operators.
With these remarks, we conclude this chapter.
#### 3 A Brief Introduction to Linear Wave Equations
##### Introduction to Hyperbolic Partial Dierential Equations
Partial Dierential Equations (PDEs) are typically categorized into three groups: elliptic, parabolic, and hyperbolic PDEs. Generally speaking, elliptic PDEs describe stationary processes that do not change over time or are time-independent alto- gether. Parabolic and hyperbolic PDEs appear in evolution equations where the state of a system changes over time. Diusion processes such as particle diusion, heat conduction, reaction-diusion and convection-diusion phenomena are typically modeled by parabolic PDEs. Hyperbolic PDEs on the other hand describe wave-like phenomena. They can be characterized by a so-called *nite speed of propagation*. This means that any initial disturbance of an equilibrium is propagated through space and time at a nite speed. Such a disturbance could be an oscillation of some sort, for instance the vibration of a string or the displacement of a church spire due to violent storm. It could also be information being sent through some homogeneous or non-homogeneous medium like a radio or telecommunication signal.
Hyperbolic PDEs are linked to so-called *conservation laws* or *balance laws*. These laws stipulate that the rate of change of the total amount of a quantity inside a xed domain is balanced by the ux of the quantity across the boundary of the domain, or in absence of any ux, conserved within the domain [77, p. 3]. Typical examples of conservation laws include the *conservation law of linear momentum* that states that the total momentum in any closed system remains constant, the *conservation of* *electric charge* that stipulates that the total electric charge in an isolated system does not change, or the well-known fundamental principle of *conservation of energy* [35, Chap. 2]. Conservation laws and balance laws are essential for our understanding of the physical world, and consequently, hyperbolic PDEs arise in a widespread range of applications.
It is common to further subdivide hyperbolic PDEs into rst and second order hy- perbolic PDEs. One distinguishing feature which can often be found in solutions for hyperbolic PDEs of rst order are *shocks*. Shocks are discontinuities in the solution that may appear after a nite period of time, even if the initial data is continuous; see for instance [43, pp. 139 sq.]. The possibility of such discontinuities necessitates rather specic and involved techniques in order to describe these equations in a mathematically rigorous and at the same time physically meaningful way. For more
<u>3 A Brief Introduction to Linear Wave Equations</u>
information on this, we refer to the very well-written introduction by Bressan [22], the standard monographs on hyperbolic conservation laws by Dafermos [35] and Lax [77], and the references therein. Second order hyperbolic PDEs are generally more benign. On one hand, they can be analyzed by techniques deemed more accessible and similar to techniques used for parabolic PDEs. On the other hand, the solutions can usually be expected to behave more regularly. In many cases, also non-trivial ones, solutions to second order hyperbolic PDEs are continuous in time, which is to say that shocks do not appear on a prescribed time interval. However, the possibility that shock waves appear, that solutions blow up after a nite time, or a non-existent altogether, is related to the nite propagation speed, and this is a feature inherent to all hyperbolic PDEs. Examples for blow-up in second order hyperbolic PDEs are for instance given in [7, 43, pp. 686 sqq., 127, Sec. 33.10].
The main focus of this thesis is the analysis of a coupled system of an abstract dierential-algebraic equation and a hyperbolic PDE. We aim to nd appropriate conditions on the coupling and the constraints that allow for continuous solutions. Therefore we concentrate on second order hyperbolic PDEs in this chapter, and we do not dive into the intricacies of rst order hyperbolic equations.
As a prototype for a second order hyperbolic PDE we choose the *linear wave equation*
′′ v − ∆v = q (3.1)
which can be used as an easy model to describe vibrating strings or membranes, or, more general, waves traveling through elastic material. To an extent, the propaga- tion of acoustic, electromagnetic, or seismic waves, usually modeled by sets of more complex equations, can also be described by wave equations. See Section 3.3 below.
##### Overview and Literature
In this chapter, we aim to give a brief introduction into the eld of linear hyperbolic equations of second order. To keep this introduction concise, we focus on one specic type of second order hyperbolic partial dierential equation, namely an abstract linear wave equation on a bounded domain. We present one way to prove existence and uniqueness of a solution, see Section 3.1. We also provide an a priori estimate that is crucial for the analysis of the coupled system in Chapter 4. In Section 3.2, we discuss the abstract linear wave equation which can be seen as a paradigm for an equation that ts into the general framework discussed before. We close this chapter by giving examples where linear wave equations, semilinear variants, and related equations appear in applications, see Section 3.3.
Accessible results for linear wave equations with homogeneous boundary conditions can be found in many textbooks on PDEs such as [43, 93, 104]. Abstract versions of linear second order hyperbolic equation, also complemented by non-homogeneous boundary conditions, can be found in the classical textbooks by Lions [81] and Lions
<u>3.1 Linear Hyperbolic Partial Dierential Equations of Second Order</u>
and Magenes [83, 84]. Variations thereof can also be found in [23, 108, 126, 127]. Regularity results on linear wave equations and general linear second order hyperbolic equations are due to Lasiecka and Triggiani and can be found in [73–76].
Results on nonlinear second order hyperbolic equations are not discussed in this chapter. We refer to the monographs of Alinhac [7] and Li and Zhou [78] and the references therein. Some results can also be found in [127, Chap. 33].
##### 3.1 Linear Hyperbolic Partial Dierential Equations of
##### Second Order
In this section, we introduce notions to properly understand the wave equations discussed in the following sections, and we present techniques in order to solve them. The presentation follows closely the elaborations of Lions and Magenes [83, Chap.
3.4 and 3.8], Schweizer [108, Chap. 12], and Zeidler [126, Chap. 24]. **Assumption 6.** Let Assumption 1 hold. Let V and H be two real Hilbert spaces, and denote with V
′ the dual space of V. Require that V is separable and that (V,H,V ′ ) forms a Gelfand triple, see Denition B.2. In particular, the embedding V ֒→ H is dense. Moreover, let a : [0,T] × V × V → R be a family of continuous bilinear forms on V such that
i) the mapping
t 7→ a(t; v,w) : [0,T] → R
is continuously dierentiable for all v,w ∈ V;
ii) a is symmetric, i. e. a(t; v,w) = a(t; w,v) for all t ∈ [0,T] and v,w ∈ V;
iii) there are λ ≥ 0 and α > 0 such that
a(t; v,v) + λ‖v‖ 2 H≥ α‖v‖ 2 V
holds for all t ∈ [0,T] and v ∈ V. In other words, a fullls an abstract Gårding’s inequality. See [126, p. 426, 39, p. 218].
Due to the continuity of a, we may then introduce a family of linear operators A(t) ∈ L(V,V ′ ) through 〈[A(t)]v,w〉 = a(t; v,w). (3.2)
We now consider the abstract linear hyperbolic partial dierential equation of second order
v ′′
(t) + A(t)v(t) = q(t) f. a. a. t ∈ [0,T], (3.3a)
<u>3 A Brief Introduction to Linear Wave Equations</u>
with initial conditions v(0) = v₀, (3.3b) v ′
(0) = v₁. (3.3c)
′
|In order to render this equation meaningful, it suces to let q ∈ L¹(0,T; V||), and let|
|||′|
|2,1 ′|′||
A(t) be given by (3.2). Then, (3.3) directly implies v ′′ ∈ L¹(0,T; V ′ ) and thus, v ∈ W (0,T; V). It follows that v and v are absolutely continuous, see Lemma B.24, and hence, the initial conditions are meaningful. Note that by slight abuse of notation we reused the variable v. This is common in this context and we will continue to do so whenever it is unambiguous.
**Perspectives on (3.3)** There are at least two dierent mathematical perspectives on partial dierential equations such as (3.3), which we call the *operator perspective* and the *variational perspective*. Understanding the PDE in an operator sense, we try to nd an appropriate framework to ensure that the appearing dierential operators are as nice as possible, for instance isomorphisms. This approach seems natural in light of classical solutions for PDEs when dierential operators can be meaningfully dened in a strong sense. To discuss wellposedness of the PDE as well as existence of solutions then eectively means to establish an understanding of the operators present in the PDE, by indicating specic domain and codomain spaces, or features the operators ought to have. Oftentimes a connection to the variational perspective can be established through the denition of certain inner products on the operator’s domain space and establishing integration-by-parts formulas.
On the other hand, the variational perspective starts from a variational formulation which can only be understood properly if the solution and test function spaces are explicitly indicated. The variational formulation commonly contains bilinear forms or inner products and the operators appearing in the more concise formulation that is the PDE are derived from these bilinear forms, just as in Assumption 6. This approach seems, in general, to oer more exibility in the sense that solution and test function space need not to be related directly, but it makes the comparison of dierent regularity results in literature and establishing the relations between them quite challenging. Nevertheless, in light of Sobolev or Bochner spaces, and consid- ering distribution theory, the variational perspective is as common as the operator perspective.
As can be inferred from Assumption 6, we will rather take the variational perspective in the following. But this is a personal preference; both perspectives are closely related, and often it is easily possible to switch from one to the other. See for instance [83, pp. 200 sqq., 43, Chap. 8].
The next statement provides an existence and uniqueness result for the very general formulation (3.3) of a linear second order hyperbolic PDE. Note that we did not
<u>3.1 Linear Hyperbolic Partial Dierential Equations of Second Order</u>
explicitly specify boundary conditions. In fact, they are covered either by the choice of a specic solution space V or by the given bilinear form a. Note also that we did not and will not pin down a variational formulation of (3.3). The reason for this is that we do not intend to give one proof for one specic understanding of the PDE, meaning one specic variational formulation. We rather aim to indicate a general procedure of proving such an existence result. This includes a certain density argument, which is, in turn, related to the test function space for the variational formulation.
**Theorem 3.1 ([83, Thm. 8.1]).** *Let initial conditions* v₀ ∈ V *and* v₁ ∈ H *be given* *and assume the right-hand side to be* q ∈ L²(0,T; H)*. Then, there exists a unique* *function* v ∈ L²(0,T; V) ∩ H¹(0,T; H) ∩ H²(0,T; V ′ )
*satisfying* (3.3)*.*
**Sketch of Proof.** Proofs of this or similar statements can be found, among others, in the textbooks by Lions and Magenes [83, pp. 265 sqq.], Schweizer [108, pp. 219 sqq.], and Zeidler [126, pp. 452 sqq.]. They all follow the same main line of action, start- ing from a more ([108, 126]) or less ([83]) explicitly given variational formulation, and using the fundamental principle “a priori estimates yield existence” applied to approximate Galerkin equations, see also [127, pp. 1183 sq.].
By Assumption 6, V is separable. Using a Galerkin approach, we x k ∈ N and approximate (3.3) on a k-dimensional subspace V
(k) ⊂ V. We obtain a set of k
linear ordinary dierential equations with approximate initial conditions. This set of equations admits a unique solution v
(k) : [0,T] → V
(k) on all of [0,T] by virtue
of Carathéodory’s solution theory, cf. [108, p. 228, 126, p. 465, *Step 5*]. This approximate solution fullls an a priori estimate of the form
||||||∫|)|
|---|---|---|---|---|---|---|
|2|(k) ′|2|2|2||2|
|V||H|V|H||V|
||||||0||
( t ‖v
(k)
(t)‖ 2 + ‖(v
(k) ) ′
(t)‖ 2 ≤ c ‖v₀‖
2 + ‖v₁‖ 2 + ‖q(s)‖ 2 ds (3.4)
with constant c > 0 for almost all t ∈ [0,T]. Note that the right-hand side bound is independent of k. Hence, the sequence of approximate solutions (v
(k) )⊂V is
uniformly bounded. It is therefore possible to extract a subsequence that converges weakly to some v in the sense of L²(0,T; V) ∩ H¹(0,T; H).
In order to show that v is indeed a solution to the PDE (3.3), we let k → ∞ in the set of ordinary dierential equations that determines v
(k), all the while exploiting
the fact that any function v ∈ L²(0,T; V) ∩ H¹(0,T; H) can be approximated by a series of classically dierentiable functions. This could be polynomials as in [126, Sec. 24.3], or functions with compact support and certain vanishing boundary values as in [108, p. 229, 83, p. 268]. As noted above, this chosen density result eectively dictates how to understand the PDE (3.3) in view of its variational formulation.
<u>3 A Brief Introduction to Linear Wave Equations</u>
The successful limiting process shows that the weak limit point solves (3.3), and consequently proves the existence of a solution.
Uniqueness of a solution follows from the a priori estimate applied to a solution of the variational formulation of (3.3) when tested with a specic test function, see [83<u>,</u> pp. 268 sqq., 126, pp. 459 sq.]. This concludes the proof.
Of course, there are other techniques for proving similar results for similar problems such as the semigroup approach or the vanishing viscosity/parabolic regularization approach, to name only two. We will not dive into more detail here but refer to the corresponding literature, for instance [43, 77, 83, 127] and the references therein.
**Remark.** There are three remarks to be made concerning the uniqueness and the regularity of the solution. First, uniqueness of a solution to the PDE implies weak convergence of the entire series of approximate solutions (v
(k) ) and not only weak
convergence along a subsequence. See [125, p. 480, 126, p. 465] for instance. This may be relevant for the numerical computation of the solution.
Second, since the a priori estimate (3.4) holds for almost all t ∈ [0,T], we deduce that the unique solution of (3.3) has regularity
v ∈ L ∞ (0,T; V) ∩ W 1,∞ (0,T; H). (3.5)
From this, we derive the continuity of v with respect to time. More precisely, the equivalence class of solutions contains a continuous representative v ∈ C([0,T]; H); cf. Lemma B.25. Using the technique of mollication, it is even possible to prove the existence of a continuous representative
v ∈ C([0,T]; V) ∩ C¹([0,T]; H). (3.6)
See in particular the proofs of Theorems 12.5 and 12.6 in [108, pp. 230 sq.].
Third, we want to point out that this continuous representative (3.6) satises for all t ∈ [0,T] the energy equation
∫t a(t; v(t),v(t)) + ‖v ′
(t)‖ 2 H= a(0; v₀,v₀) + ‖v₁‖
2 H+ 2 a ′ (s; v(s),v(s)) ds 0 ∫t + 2 (q(s),v ′
(s)) ds. (3.7)
See [83, pp. 276 sq.] and cf. [108, pp. 228, 230]. This energy equality can be interpreted as a balance law in compliance with our introduction: The energy of the system given on the left-hand side is equal to the initial energy of the system plus the energy put into the system by means of the right-hand side function q. In other words, the total amount of energy is conserved over time within the system.
<u>3.2 Linear Wave Equations</u>
##### 3.2 Linear Wave Equations
In this section, we present the prototypical linear wave equation subject to homo- geneous Dirichlet boundary conditions in its most well-known framework. It is an example for the class of linear hyperbolic PDEs of second order discussed in Sec- tion 3.1, and it will be used as a representative of this class in Chapter 4. We will also comment on other boundary conditions.
##### 3.2.1 Homogeneous Dirichlet Boundary Conditions
The classical linear wave equation with homogeneous boundary conditions is given in the following setting which is in accordance with Assumption 6.
Let V := H₀₁(Ω) and H := L²(Ω), and denote the dual space V ′ =: H −1
(Ω) as
usual in this framework. The triple (H₀₁(Ω),L²(Ω),H −1
(Ω)) forms a Gelfand triple
with compactness, i. e. the embedding H₀₁(Ω) ֒→ L²(Ω) is even compact. See De- nition B.2.
We dene an inner product on H₀₁(Ω) through
(v,w)H 0 1
(Ω):= (∇v, ∇w)L2(Ω)
for v,w ∈ H₀₁(Ω). This is indeed an inner product as its positive deniteness is ensured by the Poincaré inequality (B.9). It induces the typical norm in H₀₁(Ω), given by √ ‖v‖H 0 1
(Ω):= (∇v, ∇v)L2(Ω),
but it will not be used otherwise. In all considerations below, (·, ·) will always denote the inner product in L²(Ω). We may now introduce the linear operator −∆ : H₀₁(Ω) → H −1
(Ω) in the same way as in (3.2) through
##### 〈−∆v,w〉 := (∇v, ∇w)L2(Ω). (3.8)
In this setting, the linear wave equation with homogeneous Dirichlet boundary con- ditions reads  ′′
(t) − ∆v(t) = q(t) f. a. a. t ∈ (0,T),
 v   v(t) = 0 on (0,T) × ∂Ω, (3.9)   v(0) = v₀ in Ω,   v ′
(0) = v₁ in Ω.
We aim to nd a function v : [0,T) × Ω that solves this equation in some sense.
<u>3 A Brief Introduction to Linear Wave Equations</u>
**Denition 3.2.** We call a function v ∈ L²(0,T; H₀₁(Ω)) ∩ H¹(0,T; L²(Ω)) a *weak* *solution* to the wave equation (3.9) if the initial condition v(0) = v₀ holds, and v satises
|∫|∫|
|---|---|
|′||
|0|0|
T T −(v ′
(t),w)ϕ ′
(t) + (∇v(t), ∇w)ϕ(t) dt = (q(t),w)ϕ(t) dt + (v₁,w)ϕ(0)
(3.10)
for all w ∈ H₀₁(Ω) and ϕ ∈ Cc1([0,T)).
We chose this denition in accordance with [83, 108]. Note that the notion of a weak solution is not necessarily unique but diers in literature. Compare for in- stance [108] and [126].
**Proposition 3.3.** *Given initial data* v₀ ∈ H₀₁(Ω) *and* v₁ ∈ L²(Ω)*, and a right-hand* *side function* q ∈ L²(0,T; L²(Ω))*, there exists a unique function*
v ∈ L²(0,T; H₀₁(Ω)) ∩ H¹(0,T; L²(Ω)) ∩ H²(0,T; H −1
(Ω)) (3.11)
*that solves* (3.9) *in the weak sense of Denition 3.2.*
*Moreover, we have*
v ∈ C([0,T]; H₀₁(Ω)) ∩ C¹([0,T]; L²(Ω)), (3.12)
*after a possible modication on a set of measure zero. This continuous representative* *fullls for all* t ∈ [0,T] *the energy equation* ∫t
|2|′ 2|2|2||
|---|---|---|---|---|
|H (Ω)|L (Ω)|H (Ω)|L (Ω)||
|||||0|
‖v(t)‖ 2 1 + ‖v ′
(t)‖ 2 2 = ‖v₀‖
2 1 + ‖v₁‖ 2 2 + 2 (q(s),v ′
(s)) ds. (3.13)
0 0
**Proof.** A direct proof is given in [43, Sec. 7.2]. It uses the same ideas as the proof of Theorem 3.1. The regularity result (3.12) and the energy equation (3.13) are special cases of (3.6) and (3.7). See the remark on page 46 and also [108, pp. 230 sq., 83, pp. 276 sqq.].
**Remark.** Using the symbol −∆ for the operator dened in (3.8) is, of course, not accidental. From a mathematical point, this denition is absolutely sound but we should explain the connection to the dierential operator
∑ d <u>∂</u> 2 <u>v</u> ∆v := 2, ∂x i i=1
##### denoted by the same symbol.
<u>3.2 Linear Wave Equations</u>
To this end, assume that the weak solution v of Proposition 3.3 is Fréchet dieren- tiable with respect to the spatial variables, i. e. v(t) ∈ C²(Ω). Then, v(t) vanishes on the boundary by the Theorem by Meyers and Serrin B.9. Therefore, Green’s identity (B.10) reads ∫ ∫ <u>∂v</u> 〈∆v(t),w〉 + (∇v, ∇w) dx = w dσ = 0. Ω ∂Ω∂ν
with w ∈ Cc1(Ω). From this equality, using (3.8), (3.9), (3.11), and the consistent structure of the Gelfand triple, see Denition B.2, we deduce that ∫ (∆v(t),w) + (q(t) − v ′′
(t),w) dx = 0
Ω
holds, thus v ′′
(t) − ∆v(t) = q(t) almost everywhere in Ω. In other words: If v is
suciently regular, the classical spatial Laplacian is recovered, and in this way, the solution theory is consistent with classical theory. For more information on this notion of consistency, that is, the recovery of classical solutions, see [23, Sec. 9.5] or [102, Sec 2.4].
##### 3.2.2 Non-homogeneous Dirichlet Boundary Conditions
The analysis for the linear wave equation with non-homogeneous boundary condi- tions, i. e. for the equation  ′′  v
(t) − ∆v(t) = q(t) f. a. a. t ∈ (0,T),
  v(t) = vb(t) on (0,T) × ∂Ω, (3.14)   v(0) = v₀ in Ω,   v ′
(0) = v₁ in Ω.
can be traced back to the homogeneous case if the boundary data vbis suciently regular. This method is often called *homogenization*. Assume that vb(t) can be extended as a H¹-function to the interior of the domain Ω. In other words, suppose there is a function v˜b∈ L²(0,T; H¹(Ω)) such that v˜b(t) = v(t) on the boundary ∂Ω for almost all t ∈ [0,T]. This relationship can also be expressed by writing 1 /2 v˜b(t) ∈ H (∂Ω). We may then look for solutions to (3.14) that lie in the set {} K := v ∈ L²(0,T; H¹(Ω)), such that v − v˜b∈ L²(0,T; H₀₁(Ω)).
Note that in order to derive an appropriate variational formulation, the PDE (3.14) is usually tested with functions w ∈ H₀₁(Ω) or w ∈ D(Ω), i. e. functions with vanishing boundary values. This leads to variational formulations similar to (3.10) with the slight but decisive dierence that we look for solutions that lie in K instead of L²(0,T; H₀₁(Ω)).
<u>3 A Brief Introduction to Linear Wave Equations</u>
##### 3.2.3 Other Boundary Conditions
Solutions to the linear wave equation and more general second order hyperbolic equa- tions with other boundary conditions such as Neumann or mixed boundary condi- tions have been extensively studied by Lasiecka and Triggiani, see for instance [73– 76]. They continue the work by Lions and Magenes [83, 84], presenting results on improved and hidden regularity of solutions as well as results on the stability of solutions. A very intelligible introduction into this topic and overview of the results is given in [74].
##### 3.3 Sample Applications
We conclude this chapter by giving two specic examples where wave equations appear in applications.
##### Electromagnetic Wave Equation
##### The four Maxwell Equations
<u>ρ</u> div E =, (3.15a) ε₀ <u>∂B</u> curl E = −, (3.15b) ∂t div B = 0, (3.15c) ( <u>∂E</u> ) curl B = µ₀ J + ε₀, (3.15d) ∂t
given here in their microscopic version, are the quintessential laws of classical electro- dynamics. *Gauss’s law for static electric elds* (3.15a) and *Gauss’s law for magnetic* *elds* (3.15c) both are balance laws: The rst one (3.15a) states that the ux of the electric eld E through a closed surface of a domain Ω is balanced by the electric charge density ρ inside the domain. The second one (3.15c) posits that the magnetic eld B is a solenoidal eld. In other words: There are no magnetic charges, or equivalently, magnetic monopoles do not, and also cannot, exist. *Faraday’s Law of* *Induction* (3.15b), relating the electric to the magnetic eld, explains in one equa- tion why dynamos work. Last but not least, *Ampère’s Circuital Law with Maxwell’s* *addition* (3.15d) links the magnetic eld to the electric current density J and it respects, through Maxwell’s additional term <u>∂E</u> ∂t, a third conservation law, namely the *conservation of charge* (cf. [46, Chap. 18]). For completeness, we mention the vacuum permittivity ε₀ and the vacuum magnetic permeability µ₀.
<u>3.3 Sample Applications</u>
Under the assumption that Ω is a region of neither electric charges (ρ = 0) nor electric currents (J = 0), as for instance in a vacuum, these equations reduce to
<u>∂B ∂E</u> div E = 0, curl E = −, div B = 0, and curl B = µ₀ε₀. (3.16) ∂t ∂t
Let us nally assume that the two eld functions B and E are suciently smooth vector elds, that is, B,E ∈ C²(R × R³, R³). Then, applying the dierential operator curl to the second and fourth equation of (3.16), and using the identity curl(curl A) = −∆A + ∇ div A for any smooth vector eld A, yields
<u>∂</u> () − curl B = curl(curl E) = −∆E + ∇ div E (3.17) ∂t as well as <u>∂</u> () µ₀ε₀ curl E = curl(curl B) = −(∆B + ∇ div B). (3.18) ∂t
Note that the three dierential operators ∇, div and curl operate on the spatial variables only, and that partial time and space derivatives permute. Finally, the rst and fourth equation of (3.16) used in (3.17), and the second and third equation of (3.16) used in (3.18) reveals
<u>∂</u> 2 <u>E ∂</u> 2 <u>B</u> µ₀ε₀ 2 − ∆E = 0 and µ₀ε₀ 2 − ∆B = 0. (3.19) ∂t ∂t
Thus, under certain assumptions, both the electric eld E, and the magnetic eld B fulll a homogeneous linear wave equation. Either of the two equations (3.19) is rightfully named *electromagnetic wave equation*.
##### Oscillation of a string or a membrane
In the case d = 1 with Ω := (0,L), L > 0, consider a horizontal string that is xed at two points ∂Ω = {0,L} in space. Under the assumption that the string has a constant tension S and a constant mass per unit length µ, the oscillation of a string can be modeled by the one dimensional wave equation
|2|2||
|2|2||
|||∂|
|||∂t|
<u>∂ S ∂</u> v(t,x) = v(t,x) for t ∈ (0,T) and x ∈ Ω, ∂t µ ∂x
subject to initial conditions v(0,x) = v₀ and v(0,x) = v₁ for x ∈ Ω, and boundary conditions v(t, 0) = v(t,L) = 0 for t > 0. The initial conditions represent the initial displacement v₀ and initial velocity v₁ of the string, and the function value v(x,t) of the solution function v : [0,T) × (0,L) → R describes the displacement of the string at time t ≥ 0 for some point of reference x ∈ (0,L). The same considerations are valid for modeling oscillations of membranes (d = 2). For more information, we refer to [51, pp. 224 sq., 264 sqq.].
<u>3 A Brief Introduction to Linear Wave Equations</u>
##### Further Examples
Further sample applications, their modeling, and the connection to the linear wave equation can be found in the textbook on partial dierential equations by Schweizer [108, pp. 22 sq., 26, sq., 219 sqq., 497 sqq.].
There are many more problems in physics, chemistry, and engineering that cannot be modeled directly by linear wave equations but by semilinear variants and other related equations. Strongly damped wave equations, which can be seen as regularized linear wave equations, are used to model longitudinal or torsional vibrations in rods, [51, Sec. 4.3.1]. Elastic wave equations such as the Navier-Cauchy equations are used in linear elasticity theory to model deformation processes of elastic materials, [51, Sec. 2.5]. In quantum mechanics, relativistic wave equations model the behavior of high energy particles. The Klein-Gordon equation for instance, which is a semilinear wave equation, describes spinless particles like pions; see [49, Chapter 1]. Also, problems in nonlinear acoustics and piezoelectricity are related to wave equations, ultimately showing its ubiquity.
##### 3.4 Summary
In this chapter, we provided a shallow insight into the eld of linear hyperbolic PDEs of second order and their applications. We presented an existence and uniqueness result for an abstract formulation, and we argued that the analysis of more specic versions can be executed along the same lines. This was done with the objective to be able to use the specic version in the analysis of a coupled system in the upcoming Chapter 4 as a representative for other linear hyperbolic PDEs of second order that fall into the same analytical framework.
#### 4 Analysis of a Coupled System
##### Introduction to Coupled Systems
Coupled systems of dierential equations appear in various elds of applications. This includes multiphysics systems where the state of the physical systems needs to be modeled by more than one type of dierential equation. It also includes cascading systems where physical systems are connected in series such that the solution to the rst actuates the second system. In this chapter, we discuss a coupled system of an abstract dierential-algebraic equation (DAE) and a partial dierential equation (PDE). Such systems appear for instance in electrical engineering as so-called circuit- eld coupled systems which become more and more important, see for instance [2–6, 107, 117]. In bio-mathematics, the blood ow through the cardiovascular system can be modeled by coupled systems of DAEs and PDEs, see for instance [67, 87, 111]. Due to the climate crisis, the interest in modeling and simulating energy transport networks is ever-increasing and the research of such and related problems has recently drawn more and more focus, see [62, 67, 116]. Coupled systems of DAEs and PDEs can often be found in literature as PDAEs, and we refer to the introduction in Chapter 2 for more information.
As promised by the title of this thesis, we want to analyze a coupled system of an abstract DAE and a hyperbolic PDE. More specically, we are interested in cou- pling an abstract DAE and a semilinear wave equation through nonlinear coupling functions. When analyzing coupled systems of dierential equations, it is necessary to take into account the nature of the dierent types of dierential equations and to compensate for it. This does not only concern the varying frameworks dierent types of dierential equations may be stated in, but also dierent notions of solu- tions, distinct analytical techniques to formulate and prove existence results, and so on. For example, already for PDEs a variety of dierent very general tools exist to treat appearing nonlinearities, such as variational methods, the method of lineariza- tion, xed-point theorems, monotonicity approaches, implicit function theorems, or compactness methods, among others; see [125, pp. 5 sqq., 127, 483 sq., Chapter 25, 43, Chapters 8 and 9]. Analyzing coupled systems of dierential equations with nonlinear coupling operators does obviously not simplify the discussion.
In this chapter, we focus on consolidating the type of abstract DAEs considered in Chapter 2, and the type of hyperbolic PDEs analyzed in Chapter 3 while foregoing individual complications. The analysis presented here has to be seen as a proof
##### <u>4 Analysis of a Coupled System</u>
of concept. Nonetheless, we will emphasize some possible points of deviation and discuss desirable extensions.
##### Overview and Literature
In this chapter, we rst analyze a coupled system of an ordinary dierential equa- tion (ODE) and a semilinear wave equation with homogeneous Dirichlet boundary conditions which reads  ′  (t) + φ₁(t,u(t),v(t)) = q₁(t) f. a. a. t ∈ (0,T), (4.1a)  u   v′′
(t) − ∆v(t) + φ (t,u(t),v(t)) = q (t)2 2f. a. a. t ∈ (0,T), (4.1b)
 on (0,T) × ∂Ω, (4.1c)  v(t) = 0    ′ (u,v,v)(0) = (u ,v ,v )0 0 1a. e. in Ω. (4.1d)
The two solution variables u and v are coupled through nonlinear coupling functions φ₁ and φ₂. The wave equation with homogeneous Dirichlet boundary conditions has to be seen as a representative for the larger class of second order hyperbolic equations discussed in Chapter 3. Afterwards, we transfer the results obtained for this system to a coupled system of abstract DAE and semilinear wave equation of the form { ′ (E u) (t) + φ₁(t,u(t),v(t)) = q₁(t) f. a. a. t ∈ (0,T), (1.1) ′′ v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t) f. a. a. t ∈ (0,T),
where the system has to complemented by appropriate initial and boundary condi- tions.
The major part of our eorts in this chapter is dedicated to analyzing the coupled system (4.1) of ODE and wave equation. In Section 4.1, we introduce a general functional framework, and in Section 4.2, we present an existence and a uniqueness result for (4.1) by means of an iteration procedure based on Banach’s Fixed-Point Theorem B.1. This is possible due to Lipschitz conditions on the nonlinear coupling functions φ₁ and φ₂. Discussing nonlinear dierential equations where the nonlinear terms fulll Lipschitz conditions is a well-established idea. Due to the fundamentality of Banach’s xed-point theorem, it can also be applied to general operator equations, see [127, Chapter 25]. In the narrower context of (4.1), this idea has successfully been applied to quasilinear wave equations, see for instance [43, Section 12.2, 100, Section 6.3], as well as to coupled systems of ODEs and parabolic PDEs, as for instance the monodomain model, see for example [34] and the references therein. In fact, Sections 4.1 and 4.2 follow the work of Court and Kunisch [34].
The requirements made in Sections 4.1 and 4.2 are rather strong but facilitate the discussion. Also, they are compatible with the assumptions made in Chapter 2. This allows to carry over the general framework and the existence and uniqueness result
<u>4.1 Solution Spaces for the Coupled System</u>
obtained for (4.1) in Sections 4.1 and 4.2 to coupled systems of abstract DAE and semilinear wave equation of the form (1.1). In this system, an abstract semilinear DAE as discussed in Chapter 2 and a semilinear wave equation are coupled. To the best of our knowledge, systems (4.1) and (1.1) have not been discussed so far in such a general framework.
Coupled systems of ODEs and hyperbolic PDEs often appear in research literature in the context of stabilizing or controlling one part of the equation by means of the other. This includes in particular motion-planning problems like in [36, 37, 45, 68, 96]. In these cases, the ODE part of the coupled system is usually stated in a nite- dimensional setting and the spatial domain of the PDE part is often one-dimensional. The equations are usually coupled linearly only. Although our framework is a bit more general, the systems discussed in the specied articles are generally directly motivated by engineering or industrial problems, and in this sense, a lot closer to real-world applications. Other results include [19, 20] where ODEs and hyperbolic conservation laws are coupled through the boundary conditions. These systems often include in particular rst-order hyperbolic equations which entail other challenges as depicted in the introduction of Chapter 3.
Coupled systems of DAEs and PDEs are used to model and simulate a large variety of physical phenomena including problems in multiphysics, exible multibody prob- lems, or ow networks like gas transport networks or electrical circuits. We refer to the introduction in Chapter 2 for more information.
##### 4.1 Solution Spaces for the Coupled System
In this section, we specify the two function spaces which are used throughout this chapter, and we state the basic assumptions on the two coupling functions φ₁ and φ₂. Prior to this, recall the function space {} H¹(0,T; L²(Ω, R r )) := u ∈ L²(0,T; L²(Ω, R r )), ∃ u ′ ∈ L²(0,T; L²(Ω, R r ))
which embeds continuously into C([0,T]; L²(Ω, R r )), see Lemma B.24. More specif- ically, functions u ∈ H¹(0,T; L²(Ω, R r )) have an absolutely continuous representa- tive. In particular, this continuous representative fullls for some positive constant c > 0 the estimation
max ‖u(t)‖L2(Ω,Rr)≤ c‖u‖H1(0,T;L2(Ω,Rr)). (4.2) t∈[0,T]
Moreover, solutions to the abstract linear wave equation are essentially bounded and have a continuous representative in the sense of (3.6). With this in mind, we introduce () X := H¹(0,T; L²(Ω, R r )), ‖·‖X
##### <u>4 Analysis of a Coupled System</u>
and () { ′ 2 } Y := v ∈ C([0,T]; H₀₁(Ω)), v ∈ C([0,T]; L (Ω)), ‖·‖Y,
##### where the norms are given through
|:= max ‖u(t)‖||+ ‖u|‖|||
|---|---|---|---|---|---|
|X t∈[0,T]|L (Ω,R|)|L (0,T;L|(Ω,R|))|
||||′|||
|Y t∈[0,T]|H (Ω)|t∈[0,T]||L (Ω)||
‖u‖X L2(Ω,Rr) ′ L2(0,T;L2(Ω,Rr))(4.3a) t∈[0,T] and ‖v‖ := max ‖v(t)‖ 0 1 + max ‖v (t)‖ 2 (4.3b)
respectively. The product space X × Y shall be equipped with the corresponding 1-norm ‖(u,v)‖X ×Y:= ‖u‖X+ ‖v‖Y. (4.4)
**Lemma 4.1.** X *and* Y *are Banach spaces.*
**Proof.** We prove the result for X. The proof for Y works similarly.
It is clear that ‖·‖Xis a norm; (4.2) ensures its positive deniteness.
Let (un) ⊂ X be a Cauchy sequence. Then, by denition of the norm ‖·‖Xin (4.3), (un) is also a Cauchy sequence in C([0,T]; L²(Ω, R r )). Moreover, (u ′n ) is a Cauchy sequence in L²(0,T; L²(Ω, R r )). By completeness of both spaces, there are limit points u ∈ C([0,T]; L²(Ω, R r )) and w ∈ L²(0,T; L²(Ω, R r )) such that n→∞ ′n n→∞ un−−−−→ u and u −−−−→ w.
For all ϕ ∈ Cc1((0,T)), we have ∫T∫T un(t)ϕ ′
(t) dt = − u
′n
(t)ϕ(t) dt.
0 0 Taking the limit on both sides reveals ∫T∫T u(t)ϕ ′
(t) dt = − w(t)ϕ(t) dt
0 0
for all ϕ ∈ Cc1((0,T)). Thus, u admits a weak derivative in L²(0,T; L²(Ω, R r ))<u>,</u> therefore u ∈ X with u ′ = w and ‖un− u‖X→ 0.
**Remark.** Note that choosing the function spaces X and Y in the way we did here is neither an obvious nor the only possible choice. Rather, and as will become clear shortly, the choice of X and Y is related to the regularity of the solutions for the component equations and to the corresponding a priori estimates. For instance, in Chapter 3, we have seen that solutions to the linear wave equation are essentially bounded and even continuous in time. Confer [103, pp. 100 sq.] and also [34, p. 4].
<u>4.1 Solution Spaces for the Coupled System</u>
**Assumption 7.** Let Assumption 1 hold. Let the coupling functions
φ₁ : [0,T] × L²(Ω, R r )×L²(Ω) → L²(Ω, R r )
and
φ₂ : [0,T] × L²(Ω, R r )×L²(Ω) → L²(Ω)
be continuous and Lipschitz continuous with respect to the second and third variable. To put it in mathematical terms, assume that there are time independent constants L₁ > 0 and L₂ > 0 such that for all u₁,u₂,u ∈ L²(Ω, R r ) and all v₁,v₂,v ∈ L²(Ω)
##### ‖φ₁(t,u₁,v) − φ₁(t,u₂,v)‖L2(Ω,Rr)≤ L₁‖u₁ − u₂‖L2(Ω,Rr)(4.5a)
and
##### ‖φ₁(t,u,v₁) − φ₁(t,u,v₂)‖L2(Ω,Rr)≤ L₁‖v₁ − v₂‖L2(Ω)(4.5b)
as well as
##### ‖φ₂(t,u₁,v) − φ₂(t,u₂,v)‖L2(Ω)≤ L₂‖u₁ − u₂‖L2(Ω,Rr)(4.6a)
and
##### ‖φ₂(t,u,v₁) − φ₂(t,u,v₂)‖L2(Ω≤ L₂‖v₁ − v₂‖L2(Ω)(4.6b)
hold uniformly for all t ∈ [0,T].
**Denition 4.2.** We denote with Φ₁ and Φ₂ the corresponding generated Nemytskii operators dened through
[Φ₁(u,v)](t) := φ₁(t,u(t),v(t)) and [Φ₂(u,v)](t) := φ₂(t,u(t),v(t)) (4.7)
for abstract functions u : [0,T] → L²(Ω, R r ) and v : [0,T] → L²(Ω), and almost all t ∈ [0,T].
**Remark.** Both coupling functions φ₁ and φ₂ evidently fulll the Carathéodory con- dition given by Denition C.5. Also the growth condition stated in Denition C.6 is fullled: For φ₁, and analogously for φ₂, we have
‖φ₁(t,u,v)‖L2(Ω,Rr)= ‖φ₁(t, 0, 0) + φ₁(t,u,v) − φ₁(t, 0, 0)‖L2(Ω,Rr) ≤ ‖φ₁(t, 0, 0)‖L2(Ω,Rr)+ ‖φ₁(t,u,v) − φ₁(t, 0, 0)‖L2(Ω,Rr) ≤ ‖φ₁(t, 0, 0)‖L2(Ω,Rr)+ L₁‖(u,v)‖L2(Ω,Rr)×L2(Ω).
##### The continuity of φ₁ implies
max ‖φ₁(t, 0, 0)‖L2(Ω,Rr)< ∞. t∈[0,T]
##### <u>4 Analysis of a Coupled System</u>
Thus, estimate (C.5) holds with p = 2,q = 2, β = L₁, and γ ∈ L²(0,T) where
##### γ(t) := ‖φ₁(t, 0, 0)‖L2(Ω,Rr).
It follows from Theorem C.7 that the Nemytskii operators Φ₁ and Φ₂ satisfy
Φ₁(u,v) ∈ L²(0,T; L²(Ω, R r )) and Φ₂(u,v) ∈ L²(0,T; L²(Ω)) (4.8)
for all (u,v) ∈ L²(0,T; L²(Ω, R r )) × L²(0,T; L²(Ω)). Theorem C.7 also provides the continuity of Φ₁ and Φ₂.
##### 4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation
Before we can begin to prove existence and uniqueness of solutions to the coupled system (4.1), we need to clarify what kind of solutions we are looking for. We obtained strong solutions for the abstract semilinear DAE discussed in Chapter 2, and we aimed at weak solutions for the linear wave equation discussed in Chapter 3. Recall in particular Theorem 2.22 and Denition 3.2. Therefore, we install the following denition of a solution to the coupled system in accordance with Chapters 2 and 3.
**Denition 4.3.** Let Assumptions 1 and 7 hold. Let (u₀,v₀,v₁) ∈ L²(Ω, R r ) × H₀₁(Ω) × L²(Ω) be given initial conditions. We call a tuple (u,v) ∈ X × Y a *so-* *lution to* (4.1) if ∫t u(t) = u₀ + q₁(s) − Φ₁(u,v)(s) ds (4.9a) 0
holds for almost all t ∈ [0,T],
∫T −(v ′
(t),w)ϕ ′
(t) + (∇v(t), ∇w)ϕ(t) dt
0 ∫T = (q₂(t) − Φ₂(u,v)(t),w)ϕ(t) dt + (v₁,w)ϕ(0) (4.9b) 0
holds for all w ∈ H₀₁(Ω) and ϕ ∈ Cc1([0,T)), and the initial conditions
(u,v,v ′
)(0) = (u₀,v₀,v₁) (4.9c)
##### are fullled almost everywhere in Ω.
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> **Remark.** Functions ψ : [0,T] → H₀₁(Ω) of the form ψ(t) := ϕ(t) · w with ϕ ∈ Cc1([0,T)) and w ∈ H₀₁(Ω) are dense in the space Cc1([0,T); H₀₁(Ω)) and moreover dense in the space
{} V ˆ := ψ ∈ L²(0,T; H₀₁(Ω)), ψ′∈ L²(0,T; L²(Ω)), with ψ(T) = 0.
See [108, p. 229, 83, p. 268]. Consequently, if (4.9b) holds, then for all ψ ∈ Vˆ we also have
|∫|∫|
|---|---|
|′||
|0|0|
T T −(v ′
(t),ψ ′
(t))+(∇v(t), ∇ψ(t)) dt = (q₂(t)−Φ₂(u,v)(t),ψ(t)) dt+(v₁,ψ(0)).
Prior to proving existence of a solution, we show its uniqueness.
##### 4.2.1 Uniqueness of a Solution
**Theorem 4.4.** *Let Assumptions 1 and 7 hold, and let* (u₀,v₀,v₁)∈L²(Ω, R r ) × H₀₁(Ω) × L²(Ω) *be given initial conditions. If the coupled system* (4.1) *admits a* *solution in the sense of Denition 4.3, it is unique.*
||(2) (1)|(2)|
(1) (1) (2) (2)
**Proof.** Let (u,v) ∈ X × Y and (u,v) ∈ X × Y be two solutions to (4.1), and denote with (u,v) := (u − u,v − v
(1) )
their dierence. This tuple solves the coupled system    u ′
(t) = φ₁(t,u
(1)
(t),v
(1)
(t)) − φ₁(t,u
(2)
(t),v
(2)
(t)) f. a. a. t ∈ (0,T),
  ′′ (1) (1) (2) (2) v (t) − ∆v(t) = φ₂(t,u (t),v (t)) − φ₂(t,u (t),v (t)) f. a. a. t ∈ (0,T),   v(t) = 0 on (0,T) × ∂Ω,   ′ (u,v,v )(0) = (0, 0, 0) a. e. in Ω,
in the sense of Denition 4.3. For the remainder of this proof, let t ∗ ∈ (0,T] be xed. Multiplying the rst equation of the system by u(t) reveals
′ (
(1) (1) (2) (2)
) (u (t),u(t))L2(Ω,Rr)= φ₁(t,u (t),v (t)) − φ₁(t,u (t),v (t)),u(t) L2(Ω,Rr).
||||1|2||||
|---|---|---|---|---|---|---|---|
||||2 ddt|L (Ω,R|)|||
|||∗||||||
The left-hand side can be rewritten into ‖u(t)‖2 rby (B.16). Then, inte- grating both sides over [0,t], recalling the initial conditions for u, using the Cauchy-
##### <u>4 Analysis of a Coupled System</u>
Schwarz inequality and the Lipschitz continuity of φ₁ shows
<u>1</u>∗ 2 ‖u(t )‖ L2(Ω,Rr) 2 ∫t∗∣ ∣ ∣((1) (1) (2) (2)) ∣ ≤ ∣ φ₁(t,u (t),v (t)) − φ₁(t,u (t),v (t)),u(t) L2(Ω,Rr) ∣ dt 0 ∫t∗∣ ∣ ∣((1) (1) (2) (1)) ∣ ≤ ∣ φ₁(t,u (t),v (t)) − φ₁(t,u (t),v (t)),u(t) L2(Ω,Rr) ∣ 0 ∣ ∣ ∣((2) (1) (2) (2)) ∣ + ∣ φ₁(t,u (t),v (t)) − φ₁(t,u (t),v (t)),u(t) L2(Ω,Rr) ∣ dt ∫t∗ ∥ ∥2∥ ∥ ≤ L₁∥u(t)∥ L2(Ω,Rr) + L₁∥v(t)∥ L2(Ω) ‖u(t)‖L2(Ω,Rr)dt. 0 With Young’s inequality (B.3), we obtain ∫t∗
|∗ 2|||2||2|
|---|---|---|---|---|---|
|L (Ω,R|)||L (Ω,R|)|L (Ω)|
|||0||||
‖u(t ∗ )‖ 2 2 r ≤ L₁ 3‖u(t)‖ 2 2 r + ‖v(t)‖ 2 2 dt. (4.10)
We proceed essentially as in the proof of uniqueness for solutions to linear wave equations; see [126, Section 24.3, 43, pp. 406 sqq.]. Introduce two functions ∫t { ∗ ∗ w(t) − w(t ), for 0 ≤ t ≤ t, w(t) := v(s) ds and w(t) := 00 else.
By Lemma B.19, both w and w are absolutely continuous, classically dierentiable almost everywhere, and it holds w ′ = v and w ′ = v on (0,t ∗ ). In particular, we have
w ∈ L²(0,T; H₀₁(Ω)) ∩ H¹(0,T; L²(Ω)),
and moreover w(t ∗
) = 0 by denition. Thus, by the preceding remark on page 59, it
holds ∫t∗ −(v ′
(t), w ′
(t)) + (∇v(t), ∇w(t)) dt
0 ∫t∗ = (φ₂(t,u
(1)
(t),v
(1)
(t)) − φ₂(t,u
(2)
(t),v
(2)
(t)), w(t)) dt (4.11)
0 since v₁ = 0. Rewriting the left-hand side using the relations between v, w, and w yields ∫t∗ ∫t∗ ′
(t), w ′
|−(v|−(v|(t),v(t)) + (∇w|(t), ∇w(t)) dt|
|---|---|---|---|
|0|0|∗ 2 L (Ω) ∗ 2 L (Ω)|2 L (Ω) ∗ 2 H (Ω)|
(t)) + (∇v(t), ∇w(t)) dt =
′ ′ 0 0 <u>1 1</u> = − ‖v(t)‖ 2 − ‖∇w(0)‖ 2 2 2 <u>1 1</u> = − ‖v(t)‖ 2 − ‖w(t)‖ 1 2 20
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> by (B.16) and denition of the norm in H₀₁(Ω); see Section 3.2. Using this, (4.11) reads <u>1</u>∗ 2<u>1</u>∗ 2 − ‖v(t)‖
L2(Ω) − ‖w(t)‖
|L (Ω)||H (Ω)||
|---|---|---|---|
||t|(1)|(1)|
||0|||
H1(Ω) 2 20 ∫ ∗ = (φ₂(t,u (t),v (t)) − φ₂(t,u
(2)
(t),v
(2)
(t)), w(t)) dt.
Taking the absolute value on both sides and estimating the right-hand side similarly to before using the Cauchy-Schwarz inequality and the Lipschitz continuity of φ₂, we see that
‖v(t ∗ )‖ 2 L2(Ω) + ‖w(t ∗ )‖ 2 H01(Ω) ∫t∗()
||||+ ‖v(t)‖||dt.|
|---|---|---|---|---|---|
|||L (Ω,R|)|L (Ω)|L (Ω)|
||0|||||
≤ 2L₂ ‖u(t)‖L2(Ω,Rr) L2(Ω)‖w(t)‖L2(Ω)(4.12)
We continue by examining the integral on the right-hand side. By denition, it holds w(t) = w(t) − w(t ∗ ) on [0,t ∗]. Hence, a successive application of the triangle inequality, Poincaré’s inequality (B.9), Young’s inequalities (B.3) and (B.4) as well as inequality (B.1) reveals
∫t∗() ‖u(t)‖L2(Ω,Rr)+ ‖v(t)‖L2(Ω)‖w(t)‖L2(Ω)dt 0 ∫t∗() ≤ CP‖u(t)‖L2(Ω,Rr)+ ‖v(t)‖L2(Ω)‖w(t)‖H 0 1
(Ω)dt
0 ∫t∗() + CP‖u(t)‖L2(Ω,Rr)+ ‖v(t)‖L2(Ω)‖w(t ∗ )‖H 0 1
(Ω)dt
0 ∫t∗ 2 2<u>1</u>2 ≤ CP‖u(t)‖ L2(Ω,Rr) + ‖v(t)‖ L2(Ω) + ‖w(t)‖ H1(Ω) dt 02 0 ∫t∗ 2 1212ε∗ 2 + CP 2 ‖u(t)‖ L2(Ω,Rr) + 2 ‖v(t)‖ L2(Ω) + ‖w(t)‖ H1(Ω) dt 0ε ε 2 0 ∫t∗ 2 2<u>1</u>2 ≤ CP‖u(t)‖ L2(Ω,Rr) + ‖v(t)‖ L2(Ω) + ‖w(t)‖ H1(Ω) dt, 02 0 2 ∫t∗ ∗<u>ε</u>∗ 2<u>CP</u> 2 2 + CPt ‖w(t)‖ H1(Ω) + 2 ‖u(t)‖ L2(Ω,Rr) + ‖v(t)‖ L2(Ω) dt 20ε0
where ε > 0. Returning to (4.12) and making use of the previous estimations, we
##### <u>4 Analysis of a Coupled System</u>
nd
‖v(t ∗ )‖ 2 L2(Ω) + ‖w(t ∗ )‖ 2 H01(Ω) ∫t∗ ≤ L₂CP2‖u(t)‖ 2 L2(Ω,Rr) + 2‖v(t)‖ 2 L2(Ω) + ‖w(t)‖ 2 H1(Ω) dt 0 0 ∫t∗ ∗ 2 ∗ 2<u>2</u>2 2 + L₂CPt ε ‖w(t)‖ H1(Ω) + 2 L₂CP‖u(t)‖ L2(Ω,Rr) + ‖v(t)‖ L2(Ω) dt. 0ε 0 (4.13) We now choose √ ε := 2L2 <u>1</u> CPT
which is suciently small to absorb the H₀₁-norm of w(t ∗ ) on the right-hand side of (4.13) into the left-hand side. We thus obtain ∫t∗
|∗ 2|∗ 2||2||2|2|
|---|---|---|---|---|---|---|
|L (Ω)|H (Ω)||L (Ω,R|)|L (Ω)|H (Ω)|
|||0|||||
|||||P|||
|||||∗|||
‖v(t ∗ )‖ 2 2 + ‖w(t ∗ )‖ 2 1 ≤ C ‖u(t)‖ 2 2 r + ‖v(t)‖ 2 2 + ‖w(t)‖ 2 1 dt 0 0 (4.14) for some generic constant C > 0 depending on L₂, C, and T > 0. In particular, this positive constant C is independent of the xed t.
We conclude the proof as follows. Adding (4.10) and (4.14) gives
‖u(t ∗ )‖ 2 L2(Ω,Rr) + ‖v(t ∗ )‖ 2 L2(Ω) + ‖w(t ∗ )‖ 2 H01(Ω) ∫t∗ ≤ C ‖u(t)‖ 2 L2(Ω,Rr) + ‖v(t)‖ 2 L2(Ω) + ‖w(t)‖ 2 H1(Ω) dt 0 0
where C > 0 now also depends on the Lipschitz constant L₁ > 0. Since t ∗ was arbitrarily xed in (0,T], this estimation holds for almost all t ∗ ∈ (0,T). An appli- cation of Gronwall’s Lemma C.4 shows that u(t ∗
) = 0 and v(t
∗
) = 0 for almost all
t ∗ ∈ (0,T) and thus, we have u = 0 and v = 0 on all of [0,T] by continuity of u and
v. This proves that any solution to the coupled system (4.1) must be unique. Theorem 4.4 shows that on any time interval at most one solution to system (4.1) can exist. We continue by proving existence of a local solution under slightly modi- ed assumptions, see Assumption 8. The existence results stated in Theorems 4.10 and 4.11 are based on a xed-point iteration method. The procedure works as fol- lows: We shift the nonlinear terms onto the right-hand side, and evaluate them at the previous iterate. This yields a system of two linear equations, namely a linear ODE and a linear wave equation, which are unrelated. In other words, both equations of the system are decoupled. The newly obtained right-hand sides are, mainly due to Assumption 7 and the resulting (4.8), regular enough that existence and uniqueness of a solution to the linear ODEs is directly evident. For the linear wave equation we use the results of Chapter 3. Consequently, the decoupled linear system admits
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> a unique solution, the new iterate. Using a priori estimates, we ensure that the it- eration mapping is a contraction mapping. We conclude using Banach’s xed-point theorem. We would like to point out at this point that this procedure only allows to show existence of a local solution, i. e. there is a positive maximal time of existence Tmax>
0. However, we are able to argue that the solution may be extended to any desired nite time interval such that system (4.1) admits, in fact, a global solution.
##### 4.2.2 Linear System
Consider the system    u ′
(t) = f₁(t) f. a. a. t ∈ (0,T), (4.15a)
  v′′
(t) − ∆v(t) = f (t) f. a. a. t ∈ (0,T), (4.15b)
2   v(t) = 0 on (0,T) × ∂Ω, (4.15c)   
|′|||
||0 0|1|
(u,v,v)(0) = (u ,v ,v ) a. e. in Ω, (4.15d)
which consists of two independent linear equations. To obtain a priori bounds for the solution to this linear system that are independent of T, we consider in the following T ∈ (0, 1]. Cf. for instance [100, pp. 222 sqq.]. In our existence proofs Theorems 4.10 and 4.11, we then make use of these bounds, still considering T ∈ (0, 1]. Having found a solution on this time interval, we then discuss how to extend this solution.
**Lemma 4.5.** *Let Assumption 1 with* T ∈ (0, 1] *hold. Let the right-hand side func-* *tions* f₁ *and* f₂ *satisfy*
f₁ ∈ L²(0,T; L²(Ω, R r )) *and* f₂ ∈ L²(0,T; L²(Ω)),
*and let initial conditions* (u₀,v₀,v₁)∈L²(Ω, R r )×H₀₁(Ω) × L²(Ω) *be xed. Then,* *system* (4.15) *admits a unique solution* (u,v) ∈ X ×Y *that fullls the a priori estimate* (
||+ ‖v₀‖||+ ‖v₁‖||
|---|---|---|---|---|
|L (Ω,R|)|H (Ω) L (0,T;L|L (Ω,R))|(Ω) L (0,T;L|
‖u‖X+ ‖v‖Y≤ C ‖u₀‖ 2 r 0 1 2 ) + ‖f₁‖ 2 2 r + ‖f₂‖ 2 2(Ω))(4.16)
*with a constant* C > 0 *that does not depend on* T*.*
**Proof.** As stated before, both equations can be solved independently. Since f₁ is Bochner-integrable by assumption, the function ∫t u(t) := u₀ + f₁(s) ds (4.17) 0
##### <u>4 Analysis of a Coupled System</u>
is absolutely continuous, see Lemma B.19. It is classically dierentiable almost everywhere, and it holds u ′ = f₁ for almost all t ∈ [0,T]. In particular, u ∈ X. In addition, the initial condition is fullled. Note that the solution is unique by Lemma B.23: If there was a second function u¯ ∈ X satisfying (4.15a), then there would be some u¯0such that ∫t u¯(t) = u¯0+ f₁(s) ds. 0
But then, by virtue of the initial condition, u¯ = u. From (4.17), we deduce for t ∈ [0,T]
∫t ‖u(t)‖L2(Ω,Rr)≤ ‖u₀‖L2(Ω,Rr)+ ‖f₁(s)‖L2(Ω,Rr)ds 0 2 r 2 2 r
||≤ ‖u₀‖||+ ‖f₁‖|||
|---|---|---|---|---|---|
|||L (Ω,R|)|L (0,T;L|(Ω,R))|
|L (Ω,R|)|L (Ω,R|)|L (0,T;L|(Ω,R))|
=⇒ max ‖u(t)‖ 2 r ≤ ‖u₀‖ 2 r + ‖f₁‖ 2 2 r, t∈[0,T]
and thus, u complies with the estimate
##### ‖u‖X≤ ‖u₀‖L2(Ω,Rr)+ 2‖f₁‖L2(0,T;L2(Ω,Rr)). (4.18)
The initial conditions v₀ and v₁ and the right-hand side function f₂ fulll the as- sumptions of Proposition 3.3. Consequently, there exists a unique function
v ∈ L²(0,T; H₀₁(Ω)) ∩ H¹(0,T; L²(Ω)) ∩ H²(0,T; H −1
(Ω))
which satises the energy equation (3.13). We deduce using the Cauchy-Schwarz inequality
‖v(t)‖ 2 H1(Ω) + ‖v ′
(t)‖ 2 L2(Ω)
0 ∫t = ‖v₀‖ 2 H1(Ω) + ‖v₁‖ 2 L2(Ω) + 2 (f₂(s),v ′
(s)) ds
0 0 ∫t ≤ ‖v₀‖ 2 H1(Ω) + ‖v₁‖ 2 L2(Ω) + 2 ‖f₂(s)‖L2(Ω)‖v ′
(s)‖L2(Ω)ds
0 0 ∫t ≤ ‖v₀‖ 2 H1(Ω) + ‖v₁‖ 2 L2(Ω) + ‖f₂(s)‖ 2 L2(Ω) + ‖v ′
(s)‖ 2 L2(Ω) ds
0 0 ∫t ≤ ‖v₀‖ 2 H1(Ω) + ‖v₁‖ 2 L2(Ω) + ‖f₂‖ 2 L2(0,T;L2(Ω)) + ‖v ′
(s)‖ 2 L2(Ω) ds.
0 0
It now follows from Gronwall’s Lemma C.4 that ()
|2|′ 2|2|2|2|
|---|---|---|---|---|
|H (Ω)|L (Ω)|H (Ω)|L (Ω)|L (0,T;L|
‖v(t)‖ 1 + ‖v (t)‖ 2 ≤ e T ‖v₀‖ 1 + ‖v₁‖ 2 + ‖f₂‖ 2 2
(Ω)).
0 0
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> Since T ≤ 1 holds by assumption, and by using (B.2), we obtain
() 1 /2 ‖v(t)‖H 0 1
(Ω)≤ e ‖v₀‖H01(Ω)+ ‖v₁‖L2(Ω)+ ‖f₂‖L2(0,T;L2(Ω))
as well as
||(||||)|
|---|---|---|---|---|---|
|′|/|||||
|L (Ω)||H (Ω)|L (Ω)|L (0,T;L|(Ω))|
1 2 ‖v (t)‖ 2 ≤ e ‖v₀‖ 0 1 + ‖v₁‖ 2 + ‖f₂‖ 2 2.
We can sum these two estimations, and since the bounds hold uniform in t, we nd () 1 /2 ‖v‖Y≤ 2e ‖v₀‖H
|+ ‖v₁‖|+ ‖f₂‖||.|
|---|---|---|---|
|H (Ω)|L (Ω)|L (0,T;L|(Ω))|
||||/|
0 1
(Ω) L2(Ω) L2(0,T;L2(Ω))(4.19)
1 2 Estimate (4.16) now follows from (4.18) and (4.19) with C := 2e.
##### 4.2.3 Bounds on Nemytskii Operators
Next, we present a couple of auxiliary lemmas and estimations to handle the non- linear terms within the xed-point iteration. Essentially, these estimations allow to control the solution to the coupled system by shrinking its time interval of existence. In this way, we can ensure that the iteration mapping is a contraction, and thus, the iteration is guaranteed to converge.
**Lemma 4.6.** *Let* V *be a real Banach space, and let* u ∈ H¹(0,T; V)*. Then, it holds* 1 /2
||′|
|---|---|
|L (0,T;V)|L (0,T;V)|
‖u‖ 2 ≤ T ‖u(0)‖V+ T ‖u ‖ 2.
**Proof.** This result and its proof are taken from [34, p. 8].
By Lemma B.23 and the remark on page 113, we have for almost all t ∈ [0,T] ∫t u(t) = u(0) + u ′
(s) ds.
0 A combined application of Minkowski’s inequality (B.6), the triangle inequality, (B.2), and Hölder’s inequality (B.5) shows
(∫)1/2[∫
(∫)2
]1/2 T T t ‖u‖L2(0,T;V)≤ ‖u(0)‖ 2 Vdt + ‖u ′
(s)‖Vds dt
0 0 0 [∫
(∫)(∫)
]1/2 T t t 1 /2 2 ′ 2 ≤ T ‖u(0)‖V+ 1 ds ‖u (s)‖Vdt 0 0 0 [∫ ∫]1/2 T T 1 /2 ′ 2 ≤ T ‖u(0)‖V+ t dt ‖u (s)‖Vds 0 0 1 /2 ′ = T ‖u(0)‖V+ T ‖u ‖L2(0,T;V).
##### <u>4 Analysis of a Coupled System</u>
**Lemma 4.7.** *Let Assumption 7 hold. Let* Φ₁ *be the Nemytskii operator of* (4.7)*,* *generated by* φ₁*, and denote with* L₁ > 0 *the Lipschitz constant of* φ₁*. Then, for all* u₁,u₂,u ∈ X *and* v₁,v₂,v ∈ Y *it holds*
‖Φ₁(u₁,v) − Φ₁(u₂,v)‖L2(0,T;L2(Ω,Rr)) () 1 /2 ≤ L₁ max{T,T} ‖u₁(0) − u₂(0)‖L2(Ω,Rr)+ ‖u₁ − u₂‖X(4.20)
*and*
1 /2 ‖Φ₁(u,v₁)−Φ₁(u,v₂)‖L2(0,T;L2(Ω,Rr)) P Y. (4.21)
|||≤ C|L₁T ‖v₁ − v₂‖|
|---|---|---|---|
|P P|L (0,T;L|(Ω,R))|P|
*The constant* C > 0 *is the constant that appears in the Poincaré inequality* (B.9)*.* *Note that* C *does not depend on* T *but on* Ω *only. See Theorem B.11.*
**Proof.** To show (4.20), we estimate using (4.5) and Lemma 4.6
(∫)1/2 T ‖Φ₁(u₁,v)(t) − Φ₁(u₂,v)(t)‖
2 L2(Ω,Rr) dt 0
(∫)1/2 T
2 = ‖φ₁(t,u₁(t),v(t)) − φ₁(t,u₂(t),v(t))‖ L2(Ω,Rr) dt 0 ( ∫
)1/2
T ≤ L²1‖u₁(t) − u₂(t)‖ 2 L2(Ω,Rr) dt 0 = L₁‖u₁ − u₂‖L2(0,T;L2(Ω,Rr)) () 1 /2 ′1 ′2
||‖u₁(0) − u₂(0)‖ T|||+ T ‖u|− u ‖|||
|---|---|---|---|---|---|---|---|
||||L (Ω,R|)|L|(0,T;L (Ω,R|))|
|||/||L (Ω,R|)|X||
≤ L₁L2(Ω,Rr) L2(0,T;L2(Ω,Rr)) () 1 2 ≤ L₁ max{T,T} ‖u₁(0) − u₂(0)‖ 2 r + ‖u₁ − u₂‖.
For (4.21), we nd analogously and by means of (B.9)
(∫)1/2 T
|‖Φ₁(u,v₁)(t) − Φ₁(u,v₂)(t)‖|dt||||
|---|---|---|---|---|
|0|L (Ω)|P P|L (0,T;L L|(Ω)) (0,T;H (Ω)) Y|
L2(Ω) ≤ L₁‖v₁ − v₂‖L2(0,T;L2(Ω)) 0 ≤ L₁C ‖v₁ − v₂‖ 2 0 1 1 /2 ≤ C L₁T ‖v₁ − v₂‖.
Recall that v₁ − v₂ is essentially bounded by denition of Y.
**Lemma 4.8.** *Let* Φ₂ *be the Nemytskii operator of* (4.7)*, generated by* φ₂*, and denote* *with* L₂ *the Lipschitz constant of* φ₂*. Then, it holds for all* u₁,u₂,u ∈ X *and*
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u>
##### v₁,v₂,v ∈ Y
‖Φ₂(u₁,v) − Φ₂(u₂,v)‖L2(0,T;L2(Ω)) () 1 /2 ≤ L₂ max{T,T} ‖u₁(0) − u₂(0)‖L2(Ω,Rr)+ ‖u₁ − u₂‖X(4.22)
*and* 1 /2 ‖Φ₂(u,v₁)−Φ₂(u,v₂)‖L2(0,T;L2(Ω))≤ CPL₂T ‖v₁ − v₂‖Y. (4.23)
*Again,* CP> 0 *is the Poincaré constant of* (B.9) *which is independent of* T*.*
**Proof.** Analogously to the proof of Lemma 4.7.
**Corollary 4.9.** *Lemmas 4.7 and 4.8 entail the estimation*
‖Φ₁(u₁,v₁)−Φ₁(u₂,v₂)‖L2(0,T;L2(Ω,Rr))+ ‖Φ₂(u₁,v₁)−Φ₂(u₂,v₂)‖L2(0,T;L2(Ω)) ( 1 /2 ≤ max{CP‖u₁(0) − u₂(0)‖L2(Ω,Rr) X
|, 1} max{L₁,L₂} max{T||,T}||+ ‖u₁ − u₂‖||
|---|---|---|---|---|---|
|P|||L (Ω,R|)|X|
|||||Y||
|P||||||
) + ‖v₁ − v₂‖ (4.24)
*where* C > 0 *denotes the Poincaré constant of* (B.9) *which is independent of* T*.*
##### Proof. Estimations (4.20) and (4.21) imply
‖Φ₁(u₁,v₁)−Φ₁(u₂,v₂)‖ 2 2 r
|L (0,T;L|(Ω,R))||||
|---|---|---|---|---|
|/|L (0,T;L|(Ω,R)) L (Ω,R)|L (0,T;L X|(Ω,R))|
||||/ P|Y|
≤ ‖Φ₁(u₁,v₁)−Φ₁(u₂,v₁)‖ 2 2 r + ‖Φ₁(u₂,v₁)−Φ₁(u₂,v₂)‖ 2 2 r () 1 2 ≤ L₁ max{T,T} ‖u₁(0) − u₂(0)‖ 2 r + ‖u₁ − u₂‖ 1 2 + C L₁T ‖v₁ − v₂‖.
##### Similarly, (4.22) and (4.23) imply
‖Φ₂(u₁,v₁)−Φ₂(u₂,v₂)‖L2(0,T;L2(Ω)) ≤ ‖Φ₂(u₁,v₁)−Φ₂(u₂,v₁)‖L2(0,T;L2(Ω)) + ‖Φ₂(u₂,v₁)−Φ₂(u₂,v₂)‖L2(0,T;L2(Ω)) () 1 /2
|,T} ‖u₁(0) − u₂(0)‖|||+ ‖u₁ − u₂‖|||
|---|---|---|---|---|---|
|||L (Ω,R|)|X||
|||||/||
||||||Y|
≤ L₂ max{TL2(Ω,Rr) X 1 2 + CPL₂T ‖v₁ − v₂‖.
##### Estimation (4.24) follows immediately.
##### <u>4 Analysis of a Coupled System</u>
##### 4.2.4 Local Existence for System (4.1)
In this section, we prove existence of a solution to the coupled system (4.1). As mentioned before, the result is a local one. This means that the solution only exists up to a certain maximal point in time Tmax> 0. Since Tmaxis not known beforehand, we need to slightly tweak the regularity assumptions on the coupling functions φ₁ and φ₂, see Assumption 8. This is, however, quite common in the broader scheme of things. See for instance [34, p. 9, 43, p. 663, 100, p. 222].
For our rst existence result presented as Theorem 4.10 we need another additional assumption on φ₁ and φ₂, see (4.25). Such an assumption also often appears in liter- ature, for example in [34, p. 10, 43, p. 663, 100, p. 215]. Our second existence result, given as Theorem 4.11, is based on Theorem 4.10 but shows that this additional assumption can quite easily be relaxed.
**Assumption 8.** Let Assumption 1 hold. Since the maximal time Tmax> 0 is not known beforehand, we need the following requirements to hold.
i) The right-hand side functions q₁ and q₂ need to fulll q₁ ∈ L²loc(0, ∞; L²(Ω, R
r )) and q₂ ∈ L²loc(0, ∞; L²(Ω)).
Essentially, both need to be square-integrable on any compact time interval [0,T] ⊂ [0, ∞).
ii) For the coupling functions φ₁ and φ₂, we assume that
φ₁ : [0, ∞) × L²(Ω, R r )×L²(Ω) → L²(Ω, R r )
and
φ₂ : [0, ∞) × L²(Ω, R r )×L²(Ω) → L²(Ω)
are continuous and Lipschitz continuous with respect to the second and third vari- able, see (4.5) and (4.6) of Assumption 7. As before, the Lipschitz constants L₁ > 0 and L₂ > 0 need to be uniform in time.
**Theorem 4.10.** *Let Assumptions 1 and 8 hold. In addition, assume that for all* t ∈ [0,T] *the coupling functions fulll*
φ₁(t, 0, 0) = 0 *and* φ₂(t, 0, 0) = 0. (4.25)
*Suppose initial conditions* (u₀,v₀,v₁)∈L²(Ω, R r )×H₀₁(Ω) × L²(Ω)*.*
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> *Then, there exists a maximal time* Tmax> 0 *such that for any positive* T < Tmax*the* *coupled system* 
′   u (t) + φ₁(t,u(t),v(t)) = q₁(t) *f. a. a.* t ∈ (0,T),   ′′ v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t) *f. a. a.* t ∈ (0,T), (4.1)   v(t) = 0 *on* (0,T) × ∂Ω,   (u,v,v ′
)(0) = (u₀,v₀,v₁) *a. e. in* Ω
*admits a weak solution in the sense of Denition 4.3.*
**Proof.** We prove the statement using a nested iteration procedure. The inner itera- tion provides a unique solution by means of Banach’s xed-point theorem. In order to apply this theorem, we need to consider the coupled system on a suciently small time interval. In the outer iteration, we try to extend the time interval by restarting the inner iteration with dierent initial values. It may happen that in each outer iteration the possible extension gets smaller every cycle, thus providing existence of a solution only up to a possibly nite maximal time Tmax.
*Inner Iteration* Let us rst dene the xed-point iteration procedure. For this, we set T := 1, meaning, we consider system (4.1) on the time interval [0, 1] only. In a sense, T = 1 is an initial guess up to which point in time a solution might exist. In the course of this proof, we might need to reduce T further but for now, xing it in this way shall suce. In any case, it means that the assumptions of Lemma 4.5 are fullled. Next, we introduce Banach spaces () X₁ := H¹(0, 1; L²(Ω, R r )), ‖·‖X1
and ({ } ) Y₁ := v ∈ C([0, 1]; H₀₁(Ω)), v ′ ∈ C([0, 1]; L²(Ω)), ‖·‖Y1
##### with norms ‖·‖1 1
|and ‖·‖|dened similarly to (4.3) but on [0, 1] instead of [0,T].|||
|---|---|---|---|
|X|Y|||
|(k+1)|(k+1)|||
|′||(k) (k)|(k) (k)|
We then dene the following recursion: We start with (u
(0) ,v
(0) ) := (0, 0) ∈ X₁ × Y₁.
For k ≥ 0, let (u,v) be the unique solution to the linear system
u (t) = q₁(t) − φ₁(t,u (t),v (t)) f. a. a. t ∈ (0, 1), (4.26a)
v ′′
(t) − ∆v(t) = q₂(t) − φ₂(t,u (t),v (t)) f. a. a. t ∈ (0, 1), (4.26b) v(t) = 0 on (0, 1) × ∂Ω, (4.26c) (u,v,v ′
)(0) = (u₀,v₀,v₁) a. e. in Ω. (4.26d)
There are a couple of notes to be made. First, (4.26) is a system of two linear and independent equations as the right-hand sides do not depend on u nor on v. In fact,
##### <u>4 Analysis of a Coupled System</u>
for k = 0, system (4.26) corresponds to (4.15) with right-hand sides f₁ = q₁ and f₂ = q₂, and for k > 0, it corresponds to (4.15) with
f₁ = q₁ − Φ₁(u
(k) ,v
(k) ) and f₂ = q₂ − Φ₂(u
(k) ,v
(k) ).
Second, (4.26) admits a unique solution for any arbitrarily large T < ∞ as the right-hand sides always make sense by Assumption 8. And third, the next iterate (u (k+1) ,v (k+1) ) ∈ X₁ × Y₁ is well-dened by Lemma 4.5.
Lemma 4.5 also provides the a priori estimate (4.16). Applied to the rst iterate, it reads ‖u
(1) ‖X1+ ‖v
(1) ‖Y1≤ CR. (4.27)
Here, C > 0 is the constant appearing in (4.16) which is independent of T, and
R := ‖u₀‖L2(Ω,Rr)+ ‖v₀‖H 0 1
(Ω)+ ‖v₁‖L2(Ω)+ ‖q₁‖L2(0,1;L2(Ω,Rr))+ ‖q₂‖L2(0,1;L2(Ω)).
(4.28) We briey discuss the case R = 0 which means that the initial conditions and the
|||(1) (1)|
(1) (1) (0) (0)
right-hand side functions q₁ and q₂ vanish. In this case, we have (u,v) = (0, 0) ∈ X₁ × Y₁ by (4.27); thus (u,v) = (u,v). Consequently, all iterates coincide; the sequence of iterates is constant. In this case, the iteration mapping is trivially a contraction and the unique xed point (0, 0) ∈ X₁ × Y₁ is sole solution to the coupled system (4.1).
From now on, we assume R > 0. Having introduced the general iteration procedure, we expound on how to choose T suciently small. In fact, we now choose T ∈ (0, 1] such that it meets the somewhat peculiar requirement
CLT ˜/2<. (4.29) 1<u>R</u> ‖u₀‖L2(Ω,Rr)+ 2CR
Here, C˜ := max{CP, 1} > 0 and L := max{L₁,L₂}>0 appear in (4.24). Recall that the Poincaré constant CP> 0 is independent of T and the Lipschitz constants L₁ and L₂ of the two coupling functions φ₁ and φ₂ are uniform in time. Moreover, 1 /2 1/2 observe that for T ∈ (0, 1], we have T = max{T,T}. This term also appears in (4.24).
We have two remarks concerning (4.29). First, since R > 0, we can always nd a strictly positive T satisfying (4.29). In addition, the right-hand side bound is itself bounded. In fact, we have
<u>R 1</u> CR < ‖u₀‖L2(Ω,Rr)+ 2CR =⇒ <. (4.30) ‖u₀‖L2(Ω,Rr)+ 2CR C
Second, observe that if (4.29) holds for our initial guess T = 1, then we continue this proof without reducing the time interval. Otherwise, we nd a T ∈ (0, 1) that fullls (4.29), consider system (4.26) on the smaller time interval [0,T] and use function spaces X and Y as introduced in Section 4.1.
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> Next, we dene the closed set
{} B := (u,v) ∈ X × Y, ‖u‖X+ ‖v‖Y≤ 2CR. (4.31)
Identifying the iterates (u
(0) ,v
(0) ), (u
(1) ,v
(1) ) ∈ X₁ × Y₁ with their restrictions onto
the possibly smaller time interval [0,T] ⊂ [0, 1], it is clear that (u
(0) ,v
(0) ) ∈ B,
(u
(1) ,v
(1) ) ∈ B. We now show that the next iterate fullls (u
(k+1) ,v (k+1) ) ∈ B provided that (u
(k) ,v
(k) ) ∈ B.
Since every iterate is a solution to the linear system (4.26) on [0,T], the corresponding version of estimate (4.16) is valid. For (u (k+1) ,v (k+1) ), it reads
∥ (k+1) ∥ ∥ (k+1) ∥ ( ∥u ∥ + ∥v ∥ ≤ C ‖u₀‖
|+ ‖v₀‖||+ ‖v₁‖||
|---|---|---|---|
|L (Ω,R)|H₀ (Ω) (k) (k) (k) (k)|L (0,T;L L (0,T;L|L (Ω) (Ω,R)) (Ω))|
L2(Ω,Rr)1L2(Ω) X Y H₀(Ω) + ‖q₁ − Φ₁(u,v)‖ 2 2 r ) + ‖q₂ − Φ₂(u,v)‖ 2 2.
Using the triangle inequality, and the fact that q₁ and q₂ are square-integrable on every compact time interval, in particular on [0, 1], we nd
∥
|(k) (k)|||
||L (0,T;L|(Ω,R))|
|(k)|(k)||
||L (0,T;L|(Ω))|
(k+1) ∥ ∥ (k+1) ∥ ( ∥u ∥ + ∥v ∥ ≤ CR + C ‖Φ₁(u,v)‖ 2 2 r X Y) + ‖Φ₂(u,v)‖ 2 2.
We now make use of the additional assumption on the coupling functions (4.25) as well as Corollary 4.9 to nd ∥ (k+1) ∥ ∥ (k+1) ∥ (
(k) (k)
∥u ∥ + ∥v ∥ ≤ CR + C ‖Φ₁(u,v)−Φ₁(0, 0)‖ L2(0,T;L2(Ω,Rr)) X Y) + ‖Φ₂(u
(k) ,v
(k) )−Φ₂(0, 0)‖L2(0,T;L2(Ω)).
() ˜ 1 /2 (k) (k) ≤ CR + CCLT ‖u₀‖L2(Ω,Rr)+ ‖u ‖X+ ‖v ‖Y.
Finally, by (4.29) and since (u
(k) ,v
(k) ) ∈ B, we have ()
() ∥ (k+1) ∥ ∥ (k+1) ∥ <u>R</u> ∥u ∥ + ∥v ∥ < CR + C ‖u₀‖ L2(Ω,Rr)+ 2CR X Y ‖u₀‖ 2 r + 2CR L (Ω,R) = 2CR.
|(k+1)|||
||(k)|(k)|
|(k+1)|(j)|(j)|
Thus, (u,v (k+1) ) ∈ B.
It remains to show that the iteration mapping K : B → B with (u,v) 7→ (u (k+1) ,v) is contracting. To this end, let two tuples (u
(i) ,v
(i) ), (u,v) ∈ B
be given, and consider the unique solutions
(u (i+1) ,v (i+1) ) := K(u
(i) ,v
(i) ) and (u
(j+1) ,v (j+1) ) := K(u
(j) ,v
(j) )
##### <u>4 Analysis of a Coupled System</u>
to the respective linear systems (4.26). By linearity, the dierence
(u,v) := (u (i+1) − u (j+1) ,v (i+1) − v (j+1) )
then solves the system    u ′
(t) = φ₁(t,u
(i)
(t),v
(i)
(t)) − φ₁(t,u
(j)
(t),v
(j)
(t)) f. a. a. t ∈ (0,T),
  ′′ (i) (i) (j) (j) v (t) − ∆v(t) = φ₂(t,u (t),v (t)) − φ₂(t,u (t),v (t)) f. a. a. t ∈ (0,T),   v(t) = 0 on (0,T) × ∂Ω,   ′ (u,v,v )(0) = (0, 0, 0) a. e. in Ω. (4.32) This system is still linear, is still uniquely solvable by Lemma 4.5, and its solution again fullls the corresponding version of (4.16) which in this case reads (
|(i) (i)||(j) (j)|||
|---|---|---|---|---|
||||L (0,T;L|(Ω,R))|
|(i)|(i)|(j)|(j) L (0,T;L|(Ω))|
‖u‖X+ ‖v‖Y≤ C ‖Φ₁(u,v)−Φ₁(u,v)‖ 2 2 r ) + ‖Φ₂(u,v)−Φ₂(u,v)‖ 2 2
Once more, we make use of Corollary 4.9 and obtain
||||(||||)||
|---|---|---|---|---|---|---|---|---|
||X|Y|/|(i)|(j) X|(i) (j)|Y||
|(i)|(j)||||||||
|(i+1)|(j+1)|X|(i+1)|(j+1) Y|(i)|(j) X|(i)|(j) Y|
˜ 1 2 ‖u‖ + ‖v‖ ≤ CCLT ‖u − u ‖ + ‖v − v ‖
since u and u satisfy the same initial conditions. By (4.30), () ‖u − u ‖ + ‖v − v ‖ < ‖u − u ‖ + ‖v − v ‖
holds, showing that K is a contraction. According to Banach’s Fixed-Point Theo- rem B.1, this iteration procedure converges to a unique limit point (u ∗ ,v ∗ ) ∈ B. It satises the xed-point equation (u ∗ ,v ∗ ) = K(u ∗ ,v ∗ ) which reads  ∗ ′ ∗ ∗   (u ) (t) = q₁(t) − φ₁(t,u (t),v (t)) f. a. a. t ∈ (0,T),   ∗ ′′ ∗ ∗ ∗ (v ) (t) − ∆v (t) = q₂(t) − φ₂(t,u (t),v (t)) f. a. a. t ∈ (0,T), ∗ (4.33)   v (t) = 0 on (0,T) × ∂Ω,   (u ∗ ,v ∗, (v ∗ ) ′
)(0) = (u₀,v₀,v₁) a. e. in Ω.
##### This concludes the inner iteration.
*Outer Iteration* The remainder of this proof is dedicated to showing how the solution can be extended. To this end, observe that the unique xed point (u ∗ ,v ∗ ) ∈ X × Y lies in B dened in (4.31). This implies () max ‖u ∗
|(t)‖|+ ‖v|(t)‖|) (t)‖|||
|---|---|---|---|---|---|
|L (Ω,R|)|H (Ω) L (Ω,R)|H (Ω) (0,T;L (Ω,R|L (Ω) ))|L (Ω) L (0,T;L|
L2(Ω,Rr) ∗ H01(Ω)+ ‖(v ∗ ′ L2(Ω) 0≤t≤T ( ≤ 2C ‖u₀‖ 2 r + ‖v₀‖ 0 1 + ‖v₁‖ 2 ) + ‖q₁‖L2 2 r + ‖q₂‖ 2 2(Ω)). (4.34)
<u>4.2 Analysis of a Coupled System of Abstract ODE and Semilinear Wave Equation</u> Thus, u ∗
(T), v ∗
(T), and (v
∗ ) ′
(T) are suciently regular to restart the inner iteration
procedure using these three as new initial values. We again x an initial guess T˜ = 1, redene our spaces accordingly, i. e. () X₁ := H¹(T,T + 1; L²(Ω, R r )), ‖·‖X1
and ({ } ) Y₁ := v ∈ C([T,T + 1]; H₀₁(Ω)), v ′ ∈ C([T,T + 1]; L²(Ω)), ‖·‖Y1,
begin the inner iteration with (u
(0) ,v
(0) ) := (0, 0) ∈ X₁ × Y₁ and consider for k ≥ 0
the linear system    u ′
(t) = q₁(T + t) − φ₁(T + t,u
(k)
(t),v
(k)
(t)) f. a. a. t ∈ (0, 1),
  ′′ (k) (k) v (t) − ∆v(t) = q₂(T + t) − φ₂(T + t,u (t),v (t)) f. a. a. t ∈ (0, 1),   v(t) = 0 on (0, 1) × ∂Ω,   ′ ∗ ∗ ∗ ′ (u,v,v )(0) = (u (T),v (T), (v ) (T)) a. e. in Ω.
The discussion continues as before; in particular, we reduce T˜ such that (4.29) is fullled. However, since R of (4.27) depends on the initial values, it may be possible that the bound of (4.29) becomes arbitrarily small. Consequently, in each outer iteration the possible extension of the time interval may become smaller and smaller in order to fulll (4.29) and for Banach’s Fixed-Point Theorem B.1 to be applicable. In this case, the solution may not be extended beyond a certain maximal time Tmax<u>.</u>
The following Theorem 4.11 is a consequence of Theorem 4.10 where the seemingly strong assumption (4.25) on the coupling functions is relaxed completely.
**Theorem 4.11.** *Let Assumptions 1 and 8 hold, and let initial conditions* (u₀,v₀,v₁) ∈ L²(Ω, R r )×H₀₁(Ω) × L²(Ω) *be given.*
*Then, there exists a maximal time* Tmax> 0 *such that for any positive* T < Tmax*the* *coupled system*
 ′   u (t) + φ₁(t,u(t),v(t)) = q₁(t) *f. a. a.* t ∈ (0,T),   ′′ v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t) *f. a. a.* t ∈ (0,T), (4.1)   v(t) = 0 *on* (0,T) × ∂Ω,   (u,v,v ′
)(0) = (u₀,v₀,v₁) *a. e. in* Ω
*admits a solution in the sense of Denition 4.3.*
##### <u>4 Analysis of a Coupled System</u>
**Proof.** By Assumption 8, the coupling functions φ₁ and φ₂ are continuous. Since a continuous function attains its extreme values on any closed and bounded set by Weierstrass’s extreme value theorem, the coupling functions fulll in particular
φ₁(t, 0, 0) ∈ L²loc(0, ∞; L²(Ω, R r )) and φ₂(t, 0, 0) ∈ L²loc(0, ∞; L²(Ω)).
Therefore, we may dene new right-hand side functions
q˜ 1∈ L²loc(0, ∞; L²(Ω, R r )) and q˜2∈ L²loc(0, ∞; L²(Ω))
through
q˜ 1
(t) := q₁(t) − φ₁(t, 0, 0) and q˜2(t) := q₂(t) − φ₂(t, 0, 0)
respectively. Also, we introduce two new coupling functions
φ˜1: [0, ∞) × L²(Ω, R r )×L²(Ω) → L²(Ω, R r ) and φ˜2: [0, ∞) × L²(Ω, R r )×L²(Ω) → L²(Ω)
through
φ˜1(t,u,v) := φ₁(t,u,v) − φ₁(t, 0, 0) and φ˜2(t,u,v) := φ₂(t,u,v) − φ₂(t, 0, 0).
Note that system (4.1) is equivalent to the coupled system    u ′
(t) + φ˜1(t,u(t),v(t)) = q˜1(t) f. a. a. t ∈ (0,T),
  ′′ ˜ v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q˜2(t) f. a. a. t ∈ (0,T),   v(t) = 0 on (0,T) × ∂Ω,   ′ (u,v,v )(0) = (u₀,v₀,v₁) a. e. in Ω.
Since q˜1, q˜2and φ˜1, φ˜2fulll the requirements of Assumption 8, and also abide by (4.25), Theorem 4.10 is applicable. The assertion follows immediately.
##### 4.2.5 Global Existence for System (4.1)
We will now shortly argue that the solution can, indeed, be extended to any desired nite time interval [0,Td] with Td< ∞. At the end of the proof of Theorem 4.10 we explained that in each outer iteration the current extension of the time interval of existence may become smaller and smaller. This is due to the fact that in order to apply Banach’s Fixed-Point Theorem B.1, the current extension T ∈ (0, 1] is required to fulll CLT ˜/2<.. (4.29) 1<u>R</u> ‖u₀‖L2(Ω,Rr)+ 2CR
<u>4.3 Analysis of a Coupled System of Abstract DAE and Semilinear Wave Equation</u> The positive constants C˜, L, and C are independent of time but R is not; it is inuenced by the current initial values by denition (4.28). However, a closer exam- ination of the right-hand side bound in (4.29) reveals that it is bounded from below as
1 R R ≤ ≤ 5 R + 4R ‖u₀‖L2(Ω,Rr)+ 4R
˜1/2 <u>1</u> holds. Consequently, if we choose T > 0 such that CLT < 5, the require- ment (4.29) is still satised and the length of the interval does not depend on the initial values nor on the right-hand side functions q₁ and q₂ any longer. There- fore, the outer iteration may continue to provide a solution on any desired nite time interval [0,Td] as long as q₁ and q₂ are meaningfully dened. In particular, revisiting Assumption 8, we can relax the assumptions on q₁ and q₂ and assume
q₁ ∈ L²(0,Td; L²(Ω, R r )) and q₂ ∈ L²loc(0,Td; L²(Ω)).
Note that the global solution then also fullls an estimate of the form (4.34) for a possible large C > 0. This follows from the fact that we nd a solution on any desired time interval by a nite number of outer iterations.
We have proved existence and uniqueness of a solution to the coupled system (4.1). In particular, if a solution exists, it is always unique by Theorem 4.4. Under the Lipschitz assumptions of Assumptions 7 and 8, existence of a local solution could be proved. This is comparable to the result given in [100, Chapter 6], although here, the nonlinear term of the semilinear wave equation is assumed to be suciently smooth with bounded partial derivatives. However, in comparison to [100], we were able to argue that the time interval of existence may be extended to any nite desired time interval.
In the following section, we transfer the results obtained to a coupled system of an abstract DAE and semilinear wave equation.
##### 4.3 Analysis of a Coupled System of Abstract DAE and
##### Semilinear Wave Equation
So far, the discussion in this chapter has been dedicated to the analysis of sys- tem (4.1), a coupled system of an abstract ODE and a semilinear wave equation. In this section, we make use of the results previously obtained to nally analyze a coupled system of an abstract DAE and a semilinear wave equation, namely { (E u) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t) f. a. a. t ∈ (0,T), (1.1a)
v ′′
(t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t) f. a. a. t ∈ (0,T), (1.1b)
##### <u>4 Analysis of a Coupled System</u>
subject to appropriate initial and boundary conditions.
In this system the kind of abstract DAEs which we analyzed in Chapter 2 and the kind of hyperbolic PDEs which we discussed in Chapter 3 are connected through nonlinear coupling functions φ₁ and φ₂. The analysis of the coupled system (1.1) is based on a theoretical framework similar to the one of Section 4.1. More specically, rst we utilize the techniques presented in Chapter 2 to decouple the abstract DAE in a certain way to separate its dynamic from its non-dynamic components. Using the dynamic components only, we may then formulate a second system which is related to (1.1) in a certain way but has the form of (4.1). Consequently, the theoretical results presented in Section 4.2 are applicable, providing a unique solution for the related system. From this solution and due to the index-1 character of the abstract DAE, see Chapter 2, we may then construct a solution to the original system (1.1).
In the following, we state the assumptions necessary to make this aforementioned transformation, we introduce the intermediate systems, and we explain how all sys- tems are related. As a reward for our consideration in choosing preceding assump- tions, the assumptions below are very much in line with the ones made before. Still, we make the extra eort and compile all that is required, not least to provide a meaningful starting point for future research. We also try to keep the presentation of the decoupling process as self-sucient as possible whilst keeping it ecient and concise.
**Assumption 9.** Let Assumption 1 hold. In addition, we need the following require- ments to hold.
i) Let E : L²(Ω, R
n )→L²(Ω, R n ) be a matrix-induced linear operator as in Deni- tion 2.1 such that Assumptions 2 and 3 hold.
ii) In accordance with Assumptions 4 and 8, assume that the right-hand side func- tions fulll
q₁ ∈ L²loc(0, ∞; L²(Ω, R n )) with W q₁ ∈ C([0, ∞); L²(Ω, R n )),
as well as
##### q₂ ∈ L²loc(0, ∞; L²(Ω)).
iii) As in Assumption 8, assume that the coupling functions
φ₁ : [0, ∞) × L²(Ω, R n )×L²(Ω) → L²(Ω, R n ) and φ₂ : [0, ∞) × L²(Ω, R n )×L²(Ω) → L²(Ω)
are continuous and Lipschitz continuous with respect to the second and third vari- able, see (4.5) and (4.6) of Assumption 7. As before, the Lipschitz constants L₁ > 0 and L₂ > 0 need to be uniform in time.
<u>4.3 Analysis of a Coupled System of Abstract DAE and Semilinear Wave Equation</u> The rst assumption stated in Assumption 9 allows to factorize the matrix-induced linear operator E appearing in system (1.1) using well-matched factors A and D, and to consider the system    A(Du)
′
(t) + φ₁(t,u(t),v(t)) = q₁(t) f. a. a. t ∈ (0,T), (4.35a)
  v′′
(t) − ∆v(t) + φ (t,u(t),v(t)) = q (t) f. a. a. t ∈ (0,T), (4.35b)
2 2   v(t) = 0 on (0,T) × ∂Ω, (4.35c)    (Du,v,v ′
)(0) = (u ,v ,v ) a. e. in Ω (4.35d) 0 0 1
instead. Here, the rst equation is a properly stated abstract DAE replacing the abstract DAE (1.1a), cf. (2.19) and Denition 2.13. Appropriate boundary and initial conditions are provided by (4.35c) and (4.35d). As explained in Section 2.2, it makes sense to consider as solution space for u the space {} HD 1 (0,T; L²(Ω, R n )) = u ∈ L²(0,T; L²(Ω, R n )), Du ∈ H¹(0,T; L²(Ω, R r )),
cf. Theorem 2.12, in particular (2.17). For v, we reuse the space Y introduced in Section 4.1.
In Section 2.3, we demonstrated how to split (4.35a) into the equivalent system {
||′d|−|−||−|
|---|---|---|---|---|---|
||||d|a||
||||− d|a||
|−|−|||||
|d||r|a||n−r|
|1 D|n|||||
||||− d|a||
u (t) + A φ₁(t, (D u + Qu)(t),v(t)) = A q₁(t), (4.36a)
W φ₁(t, (D u + Qu)(t),v(t)) = W q₁(t). (4.36b)
Here, A and D are specically chosen generalized inverses to A and D respec- tively, and Q and W form a pair of decoupling operators. Recall that the func- tions u ∈ H¹(0,T; L²(Ω, R)) and u ∈ L²(0,T; L²(Ω, R)) are connected to u ∈ H (0,T; L²(Ω, R)) via the relation
u = D u + Qu. (2.25)
See in particular Denitions 2.4 and 2.14, and Lemmas 2.16 and 2.17.
Next, we show how to directly solve (4.36b) with respect to the non-dynamical components of the DAE. This corresponds to an index-1 characterization of the abstract DAE (4.35a). To this end, introduce an operator
Ψ : [0,T] × L²(Ω, R r )×L²(Ω, R n−r )×L²(Ω) → L²(Ω, R n−r )
through Ψ(t,ud,ua,v) := W φ₁(t, D − ud+ Qua,v).
**Remark.** The operator Ψ is similar but slightly dierent to the operator Φ intro- duced in Assumption 4, and we use the symbol Ψ here to avoid confusion with the Nemytskii operators Φ₁ and Φ₂ from Denition 4.2.
##### <u>4 Analysis of a Coupled System</u>
**Assumption 10.** Let Assumptions 1 and 9 hold, and assume that Ψ is strongly monotone with respect to the third variable ua.
Assumption 10 has the following implication which is comparable to the result of Theorem 2.21.
**Lemma 4.12.** *Let Assumptions 1, 9, and 10 hold. Then, there exists a unique* *continuous function* g : [0,T] × L²(Ω, R r )×L²(Ω) → L²(Ω, R n−r ) *such that* (4.36b) *is fullled if and only if* ua(t) = g(t,ud(t),v(t)) (4.37)
*holds. Moreover,* g *is Lipschitz continuous with respect to its second and third* *variable.*
**Proof.** The proof is quite similar to the one of Theorem 2.21. First, the operator Ψ of Assumption 10 is continuous since φ₁ is continuous; it is Lipschitz continuous with respect to its fourth variable v since φ₁ has this property. Moreover, Ψ is also Lipschitz continuous with respect to the second variable ud∈ L²(Ω, R r ), since
##### ‖Ψ(t,ud1,ua,v) − Ψ(t,ud2,ua,v)‖L2(Ω,Rn−r)
= ‖W φ₁(t, D − ud1+ Qua,v) − W φ₁(t, D − ud2+ Qua,v)‖L2(Ω,Rn−r)
≤ ‖W‖‖φ₁(t, D − ud1+ Qua,v) − φ₁(t, D − ud2+ Qua,v)‖L2(Ω,Rn)
≤ L₁‖W‖‖D − ud1− D − ud2‖L2(Ω,Rn)
≤ L₁‖W‖‖D − ‖‖ud1− ud2‖L2(Ω,Rr).
Consequently, the operator ( 2 r 2 ) 2 n−r 2 n−r F : [0,T] × L (Ω, R)×L (Ω) × L (Ω, R)→L (Ω, R)
dened through F (t, (ud,v),ua) := Ψ(t,ud,ua,v) − W q(t)
fullls the assumptions of Theorem 2.20, which implies the existence of a unique function g with the desired properties. Since Ψ is globally Lipschitz continuous, so is F, and from the proof of Theorem 2.20 the global Lipschitz continuity of g can be directly inferred.
We may now proceed in a fashion similar to the proof of Theorem 2.22, cf. in particular system (2.35). We substitute uain (4.36a) using the relation (4.37) to obtain { u ′d
(t) + A − φ₁(t, D
− ud(t) + Qg(t,ud(t)),v(t)) = A − q₁(t), (4.38a) ua(t) − g(t,ud(t),v(t)) = 0, (4.38b)
<u>4.3 Analysis of a Coupled System of Abstract DAE and Semilinear Wave Equation</u> which is equivalent to (4.36). Note that (4.38a) depends only on dynamic variables; it is the inherent ODE of (4.35a). We now combine the inherent ODE (4.38a) and the remaining equations of system (4.35), and consider 
′d  (t) + φ˜1(t,ud(t),v(t)) = q˜1(t) f. a. a. in t ∈ (0,T), (4.39a)  u   ′′ v (t) − ∆v(t) + φ₂˜ (t,ud(t),v(t)) = q₂(t) f. a. a. in t ∈ (0,T), (4.39b)   v(t) = 0 on (0,T) × ∂Ω, (4.39c)   ′ (ud,v,v )(0) = (u₀,v₀,v₁) a. e. in Ω, (4.39d)
##### where the newly appearing functions
r r φ˜1: [0, ∞) × L²(Ω, R)×L²(Ω) → L²(Ω, R), r φ˜2: [0, ∞) × L²(Ω, R)×L²(Ω) → L²(Ω),
and r q˜1∈ L²loc(0, ∞; L²(Ω, R))
##### are dened through
− − φ˜1(t,ud,v) := A φ₁(t, D ud+ Qg(t,ud),v), −
|φ˜ (t,u|,v) := φ₂(t, D||u + Qg(t,u|
|---|---|---|---|
|2|d||d|
|||−||
||1|||
||r|||
2 d d d),v), and
q˜ (t) := A q₁(t),
for t ∈ [0,T], ud∈ L²(Ω, R) and v ∈ L²(Ω).
Note that the systems (4.35) and (4.39) are not equivalent, since it does not include the non-dynamical part of the DAE (4.36b). However, (4.39) falls into the framework of Section 4.1. In fact, we have the following existence result.
**Theorem 4.13.** *Let Assumptions 1, 9, and 10 hold. Moreover, let initial conditions* r (u₀,v₀,v₁)∈L²(Ω, R)×H₀₁(Ω) × L²(Ω) *be given.*
*Then, there exists a maximal time* Tmax> 0 *such that for any positive* T < Tmax*the* *coupled system*  ′d  (t) + φ˜1(t,ud(t),v(t)) = q˜1(t) *f. a. a. in* t ∈ (0,T),  u   ′′ v (t) − ∆v(t) + φ₂˜ (t,ud(t),v(t)) = q₂(t) *f. a. a. in* t ∈ (0,T), (4.39)   v(t) = 0 *on* (0,T) × ∂Ω*,*   ′ (ud,v,v )(0) = (u₀,v₀,v₁) *a. e. in* Ω
*admits a unique solution* (ud,v) ∈ X × Y *in the sense of Denition 4.3.*
##### <u>4 Analysis of a Coupled System</u>
**Proof.** By Lemma 4.12, the function g, which appears in the denitions of φ˜1and φ˜2, is Lipschitz continuous with respect to its second variable. From this and As- sumption 9 it follows that φ˜1and φ˜2are continuous and Lipschitz continuous with respect to the second and third variable. This is exemplied for the function φ˜1with respect to the second variable by means of
##### ‖φ˜1,v)‖ 2 r
|(t,u ,v) − φ˜|(t,u|||||||
|---|---|---|---|---|---|---|---|
|d1|1 d2|L (Ω,R)||||||
|−|− d1|d|−|− d2|d2|L (Ω,R|)|
|−|− d1|d1||− d2|d2|L (Ω,R|)|
|−|− d1|− d2|d1|d2|L (Ω,R)|||
|−|− d1|d2 L (Ω,R|)|d1|d2|L (Ω,R|)|
|−|− d1|d2 L (Ω,R|) g|d1|d2 L (Ω,R|)||
|−|−|− g|d1|d2 L (Ω,R|)|||
= ‖A φ₁(t, D u + Qg(t,u1),v) − A φ₁(t, D u + Qg(t,u),v)‖ 2 r
≤ ‖A ‖‖φ₁(t, D u + Qg(t,u),v) − φ₁(t, D u + Qg(t,u),v)‖ 2 n
≤ L₁‖A ‖‖D u − D u + Qg(t,u) − Qg(t,u)‖ 2 n () ≤ L₁‖A ‖ ‖D ‖‖u − u ‖ 2 r + ‖Q‖‖g(t,u) − g(t,u)‖ 2 n−r () ≤ L₁‖A ‖ ‖D ‖‖u − u ‖ 2 r + L ‖Q‖‖u − u ‖ 2 r () = L₁‖A ‖‖D ‖+L₁L ‖A ‖‖Q‖ ‖u − u ‖ 2 r.
Consequently, the coupled system (4.39) fullls Assumptions 7 and 8, and we deduce that (4.39) admits a unique solution (ud,v) ∈ X × Y by Theorems 4.4 and 4.11.
This result can now be used to prove existence and uniqueness of a solution to the coupled system of abstract DAE and semilinear wave equation (4.35) and as a consequence system (1.1) if appropriate initial and boundary conditions are provided.
**Theorem 4.14.** *Let Assumptions 1, 9, and 10 hold. Moreover, let initial conditions* (u₀,v₀,v₁)∈L²(Ω, R r )×H₀₁(Ω) × L²(Ω) *be given.*
*Then, there exists a maximal time* Tmax> 0 *such that for any positive* T < Tmax*the* *coupled system*    A(Du) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t) *f. a. a.* t ∈ (0,T)*,* (4.35a)
  v′′
(t) − ∆v(t) + φ (t,u(t),v(t)) = q (t) *f. a. a.* t ∈ (0,T)*,* (4.35b)
2 2   v(t) = 0 *on* (0,T) × ∂Ω*,* (4.35c)   
|′|||
||0 0|1|
|1||r|
|D|||
(Du,v,v)(0) = (u ,v ,v ) *a. e. in* Ω (4.35d)
*admits a unique solution* (u,v) ∈ H (0,T; L²(Ω, R)) × Y*.*
**Proof.** By Assumption 9 and the subsequent considerations we know how to extract from our given system (4.35) a system of the form (4.39). Theorem 4.13 then provides the existence of a unique solution (ud,v) ∈ X × Y to (4.39). The solution variable udconstitutes the dynamical part of u, and from it we recover the non-dynamical part uaof u by means of ua(t) = g(t,ud(t),v(t)). (4.37)
<u>4.4 Summary and Discussion</u>
The pair (ud,ua)∈H¹(0,T; L²(Ω, R r )) × L²(0,T; L²(Ω, R n−r )) of dynamical and non-dynamical components now solves (4.38) which is equivalent to (4.36). Using the relation
||−||
||d|a|
|1||n|
|D|||
|1||n|
|D|||
u = D u + Qu, (2.25)
we restore the variable u ∈ H (0,T; L²(Ω, R)) and since (4.36) is equivalent to DAE (4.35a), the pair (u,v) ∈ H (0,T; L²(Ω, R)) × Y is the unique solution to the coupled system (4.35).
**Remark.** As in Section 4.2.5, we argue that there exists a solution to (4.39) on any desired nite time interval. Since the implicit function g of (4.37) is even globally Lipschitz continuous by assumption on φ₁, cf. Assumption 9, this yields the existence of a unique global solution to (4.35), and consequently to (1.1).
##### 4.4 Summary and Discussion
In this chapter we analyzed a coupled system of abstract DAE and hyperbolic PDE of the form (1.1) introduced in the beginning of this thesis. The analysis presented here serves as a proof of concept for how to analyze such systems. We rst reconciled the settings for abstract DAEs and linear wave equations presented in Chapters 2 and 3 respectively, consequently looking for continuous solutions to the coupled sys- tem (1.1). We then used this framework to rst analyze the system (4.1) where instead of an abstract DAE a Banach space valued ODE and a semilinear wave equation are coupled through nonlinear coupling functions. We provided appropri- ate assumptions to prove existence and uniqueness of a solution to (4.1) by means of a xed-point iteration scheme. The existence results formulated in Theorems 4.10 and 4.11 are local ones which means that they only provide the existence of a unique solution on a possibly small time interval [0,T) with T > 0. Upon further inves- tigation on the specic upper bounds restricting the time interval, we found that this solution can be continued to any desired nite time interval; see Section 4.2.5. We then transferred the results to coupled systems of abstract DAE and wave equa- tion (1.1). The abstract DAE part of (1.1) was reformulated into an abstract DAE with properly stated leading term, see Section 2.2, resulting in system (4.35). Due to our assumptions on the abstract DAE, in particular its index-1 characteristic, we were able to retrieve the inherent abstract ODE using the technique presented in Chapter 2. Combining this inherent abstract ODE and the wave equation of (4.35) we obtained an intermediate system similar to (4.1). Thus, the previous existence and uniqueness result for (4.1) applied, and from the solution to this intermediate system we were able to retrieve a solution to the coupled system of abstract DAE and wave equation (4.35).
##### <u>4 Analysis of a Coupled System</u>
Note that in order to apply our results to realistic problems from electrical engineer- ing, bio-mathematics, or multiphysics, it will most certainly be necessary to verify certain assumptions and adapt the techniques presented here.
**Relation to other Coupled Systems and Hyperbolic Systems** In the introduction of this chapter, we indicated that the analysis of coupled systems of ODEs and hyperbolic PDEs can be motivated by so-called motion-planning problems; see e. g. [36, 37, 45, 68, 96]. Other elds of application include problems in trac control [79] or the piston problem [19, 20]. In these articles, the coupled systems take the form of a cascading system, i. e. the ODE and the PDE part of the system are usually coupled only at one part of the boundary. Thus, if the system is excited, only one part of the system is immediately aected; the second part reacts only after a certain delay. In the specied publications, the systems are rigorously analyzed using tools similar to the ones for the analysis of hyperbolic systems. Often, the solution to one part of the system can be written down explicitly leading to a delay dierential equation which is then subjected to questions of control or stabilization. It is an open topic if the extension of these techniques to coupled systems of DAEs and hyperbolic PDEs would also lead to DAEs with delay as discussed for instance in [55]. For more information regarding hyperbolic systems, we refer to [22, 35, 77].
One eld of research for coupled systems of DAEs and hyperbolic PDEs is the mod- eling, simulation, and optimization of ow networks, e. g. gas transport networks. Above, we hinted at the close connection between such coupled systems and hyper- bolic systems. And in fact, it has already been shown in [53, 54] that the gas ow through a pipe network, modeled by a system of isothermal Euler equations, can be analyzed using techniques from the analysis of hyperbolic systems. To be more explicit, the authors were able to show existence and uniqueness of a solution with- out using specic tools from DAE theory. The same holds true for the numerical analysis and discretization of such and related systems presented in [38, 52]. So, in view of our coupled system (1.1) and the analysis presented in this thesis, we would like to make two remarks. First, all pipes of the networks analyzed in [38, 52–54] are governed by the same dierential equation. It is debatable if the techniques used in the specied publications can still be used if such a network includes other also com- ponents. Second, it is well-known from DAE theory that the topology of a network directly inuences how perturbations of the initial data and force terms propagate over time. The same holds true for the discretization of such a system: As shown in [62], it is necessary to discretize such a gas transport system properly to avoid unstable numerical solutions. With respect to such questions, a DAE perspective seems unavoidable.
##### Specic Coupling Functions and the Connection to Other Second Order Semi-
**linear Wave Equations** Depending on the motivating application, semilinear wave
<u>4.4 Summary and Discussion</u>
equations take dierent forms and it might make sense to choose the coupling oper- ators, in particular φ₂, more specically. For instance, wave equations emerging in particle physics, especially nonlinear meson theory, can be of the form
v ′′
(t) − ∆v(t) + |v(t)|
ρ v(t) = 0,
for some non-critical exponent ρ ≥ 0; see [66, 82, 105] and cf. [43, pp. 677 sqq.] as well. The nonlinear term |v(t)| ρ v(t) which appears here has additional monotonicity properties. If the coupling function φ₂ is now exemplarily given as
φ₂(t,u,v) := |v| ρ v + u,
these monotonicity properties could be exploited, for instance in the limiting process of a Galerkin approach which, for suciently small ρ, is another possibility to show existence of solutions for abstract dierential equations; see e. g. [82, Chapter 1, 127, Section 33.3]. Note that Galerkin approaches have already been used to analyze coupled systems of DAEs and PDEs; cf. for instance [86, 119].
For critical power nonlinearities, i. e. if ρ is too large in comparison to the dimension of the underlying spatial domain, for dispersive wave equations like the sine-Gordon equation, or for wave equations with other types of nonlinearities, the existence the- ory may change drastically. This eects in particular the regularity of solutions, hence the choice of the coupling functions, but also the existence of essential a priori estimates like e. g. Strichartz-type estimates. We refer to the textbooks by Evans [43, pp. 688 sqq., 695 sqq.], Rauch [100, pp. 246 sqq.], Shatah and Struwe [109], and Cazenave and Haraux [30]. The analysis of nonlinear wave equations and the regu- larity of solutions has a long history which continues up to this date; see exemplary [24, 31, 110, 123].
**Further Generalizations** There are a couple of possible ways to generalize the re- sults obtained in this chapter without immoderate eort. In view of Assumptions 4 and 5, demanding the coupling operators φ₁ and φ₂ to be only locally Lipschitz con- tinuous with respect to the second and third variable but still uniform in time would allow for a considerably larger class of suitable coupling operators. The existence proof would be a bit more elaborate but since we already had to choose T suciently small to ensure existence of a local solution, we are convinced that a local Lipschitz condition instead of a global one is sucient to obtain analogous results.
We already discussed at the end of Chapter 2 how to generalize the notion of matrix- induced linear operators. This oers a way to couple even more general abstract DAEs, possible including spatial dierential operators, with other types of wave equations that do not allow for strong but only mild, weak, or other types of more irregular solutions. On the other hand, we could still exploit present network or other underlying algebraic structures through the use of matrix-induced linear operators.
##### <u>4 Analysis of a Coupled System</u>
As can be seen from the proofs of our local existence results Theorems 4.10 and 4.11, it is absolutely crucial to have a priori estimates at hand. If those are available for other types of abstract ODEs, abstract DAEs, or other second order semilinear wave equations, similar techniques to the ones presented in this chapter could be applied in order to prove existence of local solutions.
With these remarks, we conclude this chapter.
#### 5 A First Small Step Towards Optimal Control
##### Introduction, Overview, Literature
In applied sciences and applications, it is of general interest to either control or to stabilize a physical system in the most ecient way. Such problems can usually be formulated as problems of optimal control where we aim to minimize a certain cost functional subjected to side conditions.
In the previous chapter, we proved existence and uniqueness of a solution to the coupled system (4.1) where an abstract ODE and a semilinear wave equation are coupled via nonlinear coupling functions. In this chapter, we will briey investigate an optimal control problem where we aim to nd the optimal right-hand side control functions q₁ and q₂ to minimize a given cost functional. Controlling by means of the right-hand side functions rather than through boundary values means that the control is distributed and as such acts on the entire spatial domain Ω ⊂ R d. The control is allowed to be exposed to further constraints.
In Section 5.1, we formulate an optimal control problem for system (4.1), and in particular we specify the cost functional. In Section 5.2, we show existence of a global minimizer under strong assumptions on the right-hand side control functions. There are, of course, alternatives to these assumptions, some of which we discuss in Section 5.3. But as pointed out subsequently, already proving existence of an optimal control for our coupled system (4.1) is quite challenging. First-order conditions are not part of our discussion. Before we dive into the problem, we take a look at relevant literature.
There are many textbooks on optimal control with PDE constraints, for instance by Hinze, Pinnau, Ulbrich, and Ulbrich [61], Lions [81], Salsa, Vegni, Zaretti, and Zunino [104], and Tröltzsch [122]. However, due to their dierences to elliptic and parabolic PDEs, hyperbolic PDEs are rarely discussed. Few books on optimal control with DAE constraints exist, for instance by Biegler, Campbell, and Mehrmann [18], but they do not include the optimal control of abstract DAEs.
Optimal control of semilinear wave equations and more general hyperbolic equations is in itself already very challenging, and such problems have been in the focus of research interest for a long time. A selection of notable publications include arti- cles from Ismayilova [63], Kunisch and Meinlschmidt [69], Kunisch, Trautmann, and
<u>5 A First Small Step Towards Optimal Control</u>
Vexler [70], Pfa and Ulbrich [98], Schmitt and Ulbrich [106], and Zuazua [130]. Re- lated research in the narrower context of hyperbolic equations describing the gas ow through pipes, in particular Euler equations, is due to Gugat, Dick, and Leugering [52] and Gugat and Ulbrich [53, 54]; see also [56, 57]. Questions of controllability, observability, and stabilization of hyperbolic equations are discussed for instance by Coron [32], Coron and Bastin [33], Li and Zhou [78], and Triggiani [120]. We refer also to the review article by Zuazua [129] in which some challenges are presented that appear in optimal control problems with wave equations.
We already mentioned selected results for optimal control problems of coupled sys- tems of ODEs and hyperbolic equations in the last chapter, e. g. [36, 45, 68, 96], but also [19, 20, 99]. However, the research on optimal control for coupled systems of ODEs and hyperbolic equations in higher space dimensions, the research on optimal control of DAEs and hyperbolic equations, and in particular the analysis of optimal control problems with coupled systems of abstract DAEs and hyperbolic equations is largely open.
##### 5.1 Problem Formulation
We want to control the coupled system of an abstract ODE and a wave equation for which we discussed existence and uniqueness of solutions in Chapter 4. It reads
 ′   u (t) + φ₁(t,u(t),v(t)) = q₁(t) f. a. a. t ∈ (0,T),   ′′ v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t) f. a. a. t ∈ (0,T), (4.1)   v(t) = 0 on (0,T) × ∂Ω,   (u,v,v ′
)(0) = (u₀,v₀,v₁) a. e. in Ω.
**Remark.** Recall from Chapter 4 that, presuming Assumptions 1 and 8 hold, there exists for any xed control q ∈ L² loc (0, ∞; L²(Ω, R r ))×L² loc (0, ∞; L²(Ω)) a unique local solution (u,v) ∈ X × Y. As discussed in Section 4.2.5, we can extend this solution to any nite time interval [0,T], and from the proof of Theorems 4.10 and 4.11 it follows that the solution fullls the a priori estimate
()
||+ ‖v(t)‖|+ ‖v|(t)‖|||
|---|---|---|---|---|---|
|L (Ω,R|)|H (Ω) L (Ω,R)|L (Ω) H (Ω) L (0,T;L (Ω,R|L (Ω) ))|L (0,T;L|
max ‖u(t)‖L2(Ω,Rr) H 0 1
(Ω) ′
L2(Ω) 0≤t≤T ( ≤ C ‖u₀‖ 2 r + ‖v₀‖ 0 1 + ‖v₁‖ 2 ) + ‖q₁‖ 2 2 r + ‖q₂‖ 2 2(Ω))(5.1)
for some positive and possibly large constant C > 0.
<u>5.1 Problem Formulation</u>
We now x a nite T > 0 and consider the optimal control problem { min J (u,v,q) u,v,q (5.2)
s. t. (u,v) solving (4.1) with right-hand sides q = (q₁,q₂) ∈ Cad,
where Caddenotes the non-empty set of admissible controls which will be specied in Assumption 11 below. In the context of this optimal control problem, J is called the *cost functional*, q = (q₁,q₂) is the distributed control with components q₁ and q₂ corresponding to the right-hand sides of system (4.1), the tuple (u,v) is called the *state*, u and v are the *state variables*, and system (4.1) is called the *state equation*.
**Remark.** The solution spaces X and Y introduced in Section 4.1 are not ideally chosen with respect to the optimal control problem (5.2). For the analysis of this problem, we therefore consider instead of X the Hilbert space
U := H¹(0,T; L²(Ω, R r ))
with its usual norm, and instead of Y the space {} V := v ∈ L²(0,T; H₀₁(Ω)), v ′ ∈ L²(0,T; L²(Ω))
equipped with the 1-norm; cf. (B.12). Both spaces are reexive which we will exploit in the proof of our existence result stated in Section 5.2. Other possible choices are discussed at the end of this chapter. Note that the space V appears commonly in optimal control problems with wave equations; cf. e. g. [69] and the references therein.
From (5.1) in our remark above, we deduce directly that any solution (u,v) ∈ X × Y must also be bound in U × V with respect to the product 1-norm.
**Assumption 11.** Let Assumptions 1 and 8 hold. In addition, we need the following requirements to hold.
i) Let the cost functional J : U × V × Cad→ R ∪ {+∞} be given through
∫T∫T
|1|||1|||
|---|---|---|---|---|---|
||2||||2|
||L (Ω,R|)||data|L (Ω)|
|0|||0|||
||||2 L (0,T;L|(Ω,R))×L|(0,T;L (Ω))|
2 2 J (u,v,q) := ‖u(t) − udata(t)‖ 2 r dt + ‖v(t) − vdata(t)‖ 2 dt 2 2 <u>β</u> + ‖q‖ 2 2 r 2 2 (5.3) 2 with coecient β ≥ 0.
ii) Assume that the set of admissible controls
Cad⊂ L²(0,T; L²(Ω, R r )) × L²(0,T; L²(Ω))
is non-empty, convex, and compact. In particular, it is bounded and closed.
<u>5 A First Small Step Towards Optimal Control</u>
##### We introduce the following denitions.
**Denition 5.1.** A triple (u,v,q) ∈ U × V × Cadis called *a feasible point for* (5.2) if (u,v) ∈ U × V solves the coupled system (4.1) with right-hand side q ∈ Cad. In other words, the triple (u,v,q) satises the state equation. Since the state is uniquely determined for any xed control q ∈ Cad, we denote the associated state by (uq,vq).
**Denition 5.2.** An admissible control ¯q ∈ Cadis called an *optimal control* and (u¯,v¯) ∈ U × V the corresponding *optimal state* if the triple (u¯,v¯,q¯) is a feasible point, i. e. (u¯,v¯) = (u¯q,v¯q), and
##### J (u¯,v¯,q¯) ≤ J (u,v,q) (5.4)
holds for all feasible points (u,v,q) ∈ U × V × Cad.
##### 5.2 Existence of a Global Minimizer
In this section, we prove existence of a global minimizer to our optimal control problem (5.2). In this proof, we follow the outline given in [34, pp. 12 sq.]. This is possible due to the compactness of the set of admissible controls Cadprovided by Assumption 11. As mentioned already, we will discuss possible alternatives at the end of this chapter.
**Theorem 5.3.** *Let Assumptions 1, 7, 8, and 11 hold. Then, the optimal control* *problem* (5.2) *admits a global minimizer.*
**Proof.** This proof follows the general procedure for global optimal control problems, often called *direct method*; see e. g. [14, pp. 74 sqq., 61, pp. 52 sq., 54 sqq.], and compare also to [69, pp. 17 sq.].
For any chosen and xed pair of right-hand side control functions q = (q₁,q₂) ∈ Cad6= ∅, there is a unique solution (u,v) ∈ X × Y to the coupled system (4.1) by Theorems 4.4, 4.10, and 4.11. This solution also fullls (u,v) ∈ U × V. Thus, there is a feasible solution to the optimal control problem (5.2) in the sense of Denition 5.1, and since the cost functional J is bounded from below by zero, there exists an inmizing sequence (u
(k) ,v
(k) ,q
(k) ) of feasible points such that
(k) (k) (k) k→∞
J (u,v,q) −−−−→ inf J (u,v,q) > −∞. u,v,q
Note that such a sequence always exists; see e. g. [14, p. 84].
<u>5.2 Existence of a Global Minimizer</u>
By Assumption 11, the set of admissible controls Cadis compact, and thus we may
|(k)|ad||||
|---|---|---|---|---|
||∗|ad|||
|||(k)|(k)|(k)|
|∗|∗||||
extract from (q
(k) ) ⊂ Cada strongly convergent subsequence, denoted by the same
symbol, with limit point q ∈ C. The state variables are bounded with respect to the norm in U × V which follows from the energy estimate (5.1). Therefore, the boundedness of the sequence(of controls)(q) implies the boundedness of the sequence of corresponding states (u,v) ⊂ U × V. By reexivity of U × V, we may extract a weakly convergent subsequence, denoted by the same symbol, with weak limit point (u,v) ∈ U × V. Observe that the cost functional J is continuous and convex, thus weakly lower semicontinuous by Lemma B.7. Thus, we still have
lim J (u
(k) ,v
(k) ,q
(k) ) ≥ lim inf J (u
(k) ,v
(k) ,q
(k) ) = J (u ∗
,v ∗ ,q ∗
). (5.5)
k→∞ k→∞
Therefore, the limit point minimizes our cost functional. It remains to show that the
|∗ ∗ ∗|||∗ ∗||
|---|---|---|---|---|
||(k)|∗ ∗|∗ ∗|q q|
||∗||||
triple (u,v,q) is feasible. In other words, we have to show that (u,v) is a solution to the state equation (4.1) with right-hand side q, i. e. it holds (u,v) = (u ∗,v ∗).
To this end, note that the embedding H₀₁(Ω) ֒→ L²(Ω) is dense and compact; cf. Sec- tion 3.2. Then, the weak convergence v ⇀ v in the sense of L²(0,T; H₀₁(Ω)) im- plies the strong convergence v
(k) → v in the sense of L²(0,T; L²(Ω)) by Lemma B.4.
Considering the constituent terms of J in (5.3) independently, we see that therefore
|∫||∫||
|---|---|---|---|
|T (k)|2 data L (Ω)|T ∗|2 data L (Ω)|
|0||0||
k→∞ ‖v (t) − v (t)‖ 2 dt −−−−→ ‖v (t) − v (t)‖ 2 dt
holds as well as
k→∞
|(k) 2|||∗ 2|||
|---|---|---|---|---|---|
|L (0,T;L|(Ω,R))×L|(0,T;L|L (0,T;L|(Ω,R))×L|(0,T;L|
‖q ‖ 2 2 r 2 2
(Ω)) −−−−→ ‖q ‖ 2 2 r 2 2
(Ω)).
Then, it follows from (5.5) that also
|∫||||∫||||
|---|---|---|---|---|---|---|---|
|T (k)|2||k→∞|T ∗||2||
||L (Ω,R|)|||data|L (Ω,R|)|
|0||||0||||
||(k)|r ∗ (k)|(k) (k)||ad|r||
‖u (t) − udata(t)‖ 2 r dt −−−−→ ‖u (t) − u (t)‖ 2 r dt
must hold. Since L²(0,T; L²(Ω, R)) is a Hilbert space, it is uniformly convex, and weak convergence together with convergence of the norms implies strong convergence; see Lemma B.5. Thus u → u strongly in the sense of L²(0,T; L²(Ω, R)).
Now, consider a xed element (u,v,q) ∈ U × V × C of the sequence. Ac- cording to Denition 4.3 of a solution for the coupled system (4.1), it fullls Equa- tion (4.9a), i. e. for almost all t ∈ [0,T] ∫t
(k) (k) (k) (k)
u (t) = u₀ + q₁ (s) − Φ₁(u,v)(s) ds (5.6) 0
holds. Here Φ₁ is the Nemytskii operator generated by the coupling function φ₁, introduced in Denition 4.2. We recall from the proof of Lemma 4.7 that Φ₁ is
<u>5 A First Small Step Towards Optimal Control</u>
(
(k) (k) )
Lipschitz continuous and thus, the strong convergence of the sequence (u,v) in the sense of L²(0,T; L²(Ω, R r )) × L²(0,T; L²(Ω)) implies
(k) (k) k→∞ ∗ ∗
Φ₁(u,v) −−−−→ Φ₁(u,v).
Recall that (q
(k) ) converges strongly. We may therefore take the limit on both sides
of (5.6) and nd that ∫t u ∗
(t) = u₀ + q₁
∗
(s) − Φ₁(u
∗ ,v ∗ )(s) ds. (5.7) 0 ∗
|is fullled.|Note that u|is absolutely continuous by Lemma B.19, and the strong|||
|---|---|---|---|---|
||(k)|||r|
|∗ T 0|(k) ′|′|∗ (k)||
|||T (k)|(k)|(k)|
|||0|||
convergence of (u
(k) ) in the sense of L²(0,T; L²(Ω, R
r )) then immediately shows that u fullls the initial conditions, i. e. u (0) = u₀.
But, again by Denition 4.3, it holds for all w ∈ H₀₁(Ω) and for all ϕ ∈ Cc1([0,T))
∫ −((v) (t),w)ϕ (t) + (∇v (t), ∇w)ϕ(t) dt ∫ = (q₂ (t) − Φ₂(u,v)(t),w)ϕ(t) dt + (v₁,w)ϕ(0) (5.8)
where the Nemytskii operator Φ₂ is also dened in Denition 4.2. Similarly to above we argue with Lemma 4.8 that
(k) (k) k→∞ ∗ ∗
Φ₂(u,v) −−−−→ Φ₂(u,v)
holds. The weak convergence of (v
(k) ) in V implies weak convergence of ((v
(k) ) ′ )
in the sense of L²(0,T; L²(Ω)) and weak convergence of (∇v
(k) ) in the sense of
L²(0,T; L²(Ω)). Consequently, we may also take the limit in (5.8) and nd
∫T −((v ∗ ) ′
(t),w)ϕ ′
(t) + (∇v ∗
(t), ∇w)ϕ(t) dt
0 ∫T = (q₂ ∗
(t) − Φ₂(u
∗ ,v ∗ )(t),w)ϕ(t) dt + (v₁,w)ϕ(0). (5.9) 0 Finally, another compactness argument shows that v ∗ fullls the initial conditions: We already discussed that v
(k)
(0) → v ∗
(0) strongly in the sense of L²(Ω) due to the
compactness of the embedding H₀₁(Ω) ֒→ L²(Ω). But similarly, also the embedding L²(Ω) ֒→ H −1
(Ω) is compact. Thus, (v
(k) ) ′ → (v ∗
) ′ in the sense of H −1
(Ω). Thus,
we have (v ∗, (v ∗ ) ′
)(0) = (v₀,v₁) (5.10)
which by assumption even lies in H₀₁(Ω) × L²(Ω). From (5.7), (5.9), and (5.10), it follows that (u ∗ ,v ∗ ,q ∗ ) is feasible in the sense of Denition 5.1 and (5.5) shows that it is optimal in the sense of Denition 5.2. The convexity of J ensures that it is <u>a</u> global minimizer.
<u>5.3 Summary and Discussion</u>
**Remark.** If β > 0 holds, then the mapping q 7→ J (u,v,q) is strictly convex. This ensures the uniqueness of the optimal control q ∗, and moreover the uniqueness of a solution to the optimal control problem (5.2) since the state equation is also uniquely solvable.
##### 5.3 Summary and Discussion
In this chapter, we took a very brief look at an optimal control problem constrained by the coupled system (4.1) we discussed in the previous chapter. We dened one specic cost functional and formulated strong assumptions on the set of admissible controls to be able to prove existence of a unique global minimizer.
**Alternative Assumptions for Similar Results** For our existence result stated in Theorem 5.3, we required in Assumption 11 that the set of admissible controls Cad is compact. If we had demanded that Cadwas a closed, convex, and in the case β = 0 also bounded, subset of a nite-dimensional subspace of L²(0,T; L²(Ω, R r )) × L²(0,T; L²(Ω)), we could have formulated the statement in the same way without any notable modications of the proof.
The crucial point for the proof of Theorem 5.3 is the feasibility of the weak limit point. To show this, it is often necessary to nd some form of compactness crite- rion to ensure strong convergence of the extracted subsequence; either to guarantee convergence of the nonlinear terms, or to show that the limit point satises still the initial conditions. Following this reasoning, we can devise another alternative to re- stricting the admissible set of controls. Note that for the state variable v we utilized the compactness of the embedding H₀₁(Ω) ֒→ L²(Ω) but for the other state variable u such a criterion was not present. So, it would have also been possible to assume that the state variable u lies, for almost all t ∈ [0,T], in a compactly embedded sub- space of L²(Ω, R r ). We would like to refer to the article on compactness in abstract Bochner spaces by Simon [115] for more information on compactness criteria. See also the existence proof of an optimal control for a energy-critical wave equation in [69, pp. 17 sq.].
**First and Second Order Conditions** We mentioned already that this chapter is supposed to serve as a rst glimpse into the topic of optimal control. To derive suitable rst-order or even higher order conditions for this optimal control problem to eectively calculate an optimal control, a much more profound investigation is necessary. For PDE constrained optimal control problems there are several tech- niques available, for instance sensitivity approaches, adjoint approaches, and so on; see e. g. [61, 104]. For certain optimal control problems with evolution equations as side conditions, also maximum principles like the Pontryagin principle are available;
<u>5 A First Small Step Towards Optimal Control</u>
see [122, pp. 178 sqq.]. This is for instance the case for optimal control problems with semilinear parabolic equations; see [27, 101]. The same holds true for second order conditions which so far exist only for specic cases; see e. g. [28, 29]. One possible way out is to rst discretize the entire system with respect to the spatial variables by means of a Galerkin approach. This would result in a nite-dimensional ODE or DAE system, for which rst and second order conditions are more easily available. However, the downside of this approach is that the computational costs commonly depend rather strongly on the degree of discretization and the size of the discretized system. As already indicated at the end of Chapter 4, in particular for DAE systems, it is necessary to be very mindful to avoid additional undesired numerical instabilities.
#### 6 Conclusion and Outlook
In this thesis, we analyzed the coupled system { (E u) ′
(t) + φ₁(t,u(t),v(t)) = q₁(t),
′′ (1.1) v (t) − ∆v(t) + φ₂(t,u(t),v(t)) = q₂(t),
consisting of an abstract dierential-algebraic equation (DAE) and a second order hyperbolic partial dierential equation (PDE) which are coupled through nonlinear but continuous coupling functions φ₁ and φ₂.
With this thesis, we continued and complemented the research on abstract DAEs by Matthes [86] and Tischendorf [119]. We developed the notion of matrix-induced linear operators which had already appeared implicitly in research literature on ab- stract DAEs, e. g. [86] but had not yet been explicitly discussed in the context of abstract DAEs. We showed how to reformulate the semilinear abstract DAE
(E u) ′
(t) + φ(t,u(t)) = q(t) for 0 ≤ t ≤ T (2.2)
into a semilinear abstract DAE with properly stated leading term, and we transferred the decoupling approach of [64] to the innite-dimensional framework of (2.2). Due to our theoretical result presented in Theorem 2.20, we were able to develop a novel index-1-like characterization for abstract DAEs of the form (2.2), and we could show existence and uniqueness for strong solutions to (2.2), also for discontinuous right- hand side functions q.
Based on the discussion of the semilinear abstract DAE (2.2), we were able to provide a suitable framework for the coupled system (1.1). In order to prove existence and uniqueness for local and global solutions to this system, we rst analyzed a related coupled system consisting of an abstract ordinary dierential equation (ODE) and a second order hyperbolic PDE. Using a xed-point approach, we showed existence and uniqueness of local and global solutions to this related system, and afterwards, we were able to transfer the results obtained to system (1.1). Finally, we considered an optimal control problem with the related coupled system of abstract ODE and wave equation as constraint. We were able to prove existence of an optimal control and thus a minimizer to a specic cost functional.
We already indicated at the end of each chapter possible generalizations and direction for future research. Since the main goal of this thesis was the consolidation of the dierent frameworks for abstract DAEs, hyperbolic PDEs, and optimal control
##### <u>6 Conclusion and Outlook</u>
problems, most of the results we presented serve as a proof of concept. In the future, we would like to extend the notion of matrix-induced linear operators to allow also for abstract DAEs stated in a variational form, and to investigate whether these operators can keep the promise to be an eective and useful tool for the analysis of
e. g. multiphysics systems. It would also be helpful to better understand the specics and the “geometrical” meaning of the monotonicity assumptions we imposed on the nonlinear function φ in (2.2). We should also examine further the relation between our coupled system (1.1) and partial dierential-algebraic equations (PDAEs) where DAEs and PDEs are coupled. Related coupled systems where abstract DAEs are coupled with other types of semi- linear wave equations could equally be of interest for certain applications. Further, we should investigate whether the assumptions on the coupling operators could be relaxed to allow for less regular solutions or other types of nonlinearities. The research of optimal control problems as discussed in Chapter 5 is a rather open eld. We were only able to take a glimpse into the topic; already the existence proof following standard techniques required strong assumptions. Finally, we should keep our eyes open for possible elds of application to apply our theory to real-world problems.
### Appendix
#### A Generalized Inverses, Projections and Factorizations of Matrices
Generalized inverses of a real matrix E and projections onto or along the null space or the image of E are intimately related. Not only is it possible to dene such projections using generalized inverses, but it is also possible to uniquely determine a generalized inverse, given specic projections. Projections on the other hand are an important tool to decouple dierential-algebraic equations (DAEs), in particular DAEs stated in a nite-dimensional setting. Recall that the decoupling process includes separating dierentiable from non-dierentiable components of solution functions for DAEs as well as isolating dynamical and non-dynamical equations within the DAE itself. See Chapter 2 for a more elaborated description. In order to know which kind of projections are needed for a successful decoupling process, it is often helpful to rewrite a given DAE using well-matched factorizing matrices. To close the loop, well-matched factors can be constructed using generalized inverses.
Below, we present some facts on generalized inverses, projections, and factorizations of matrices and illustrate the interconnection among these three topics as much as we deem necessary for the understanding of the analysis of Chapter 2. We refer to relevant literature and advise that the notation may have been adapted to be consistent with the remainder of the thesis. Throughout this appendix, let E ∈ R m×n
be a real matrix, and denote with ker E the kernel (null space) of E, and with im E the image (range) of E.
The denitions, propositions, and relations below can be found in the textbooks on generalized inverses by Campbell and Meyer [26] and Ben-Israel and Greville [17]. They can also be found in the textbook on projection-based decoupling of DAEs by Lamour, März, and Tischendorf [72].
**Denition A.1.** Let E ∈ R m×n be a matrix. We call E − ∈ R n×m *generalized inverse* *of* E if it fullls
EE − E=E and E − EE − = E −. (A.1)
A matrix E + is called *Moore-Penrose inverse of* E if it is a generalized inverse and, in addition, fullls
( + )T + ( + )T + EE = EE and E E = E E. (A.2)
<u>A Generalized Inverses, Projections and Factorizations of Matrices</u>
**Proposition A.2.** *For any matrix* E ∈ R m×n *, the Moore-Penrose inverse* E + *is* *uniquely determined and can be constructed by means of the Singular Value Decom-* *position. In particular, any matrix* E∈R m×n *has got a generalized inverse.*
**Denition A.3.** Let a matrix P ∈ R n×n be given, and let U ⊂ R n be a subspace.
We call P *a projection* if P² = P holds.
A projection P is called *orthogonal projection* if (Pv,v − Pv) = 0 holds for all v ∈ R n×n.
A projection P is called *a projection along* U if ker P = U.
A projection P is called *a projection onto* U if im P = U.
**Proposition A.4.** *Let* U⊂R n *be a subspace. Let* P ∈ R n×n *be a projection onto*
U*. Then,* I−P∈R
n×n *is a projection along* U*.*
The next proposition reveals the promised strong relationship between generalized in- verses and projections. A proof for this fundamental result is given in [26, pp. 92 sq.].
||m×n||
||− n×m|− n×n|
|− m×m|||
|−||− +|
**Proposition A.5.** *Let* E∈R *be an arbitrary matrix.*
*i) Let a generalized inverse* E ∈ R *of* E *be xed, and dene* P := E E∈R *and* R := EE ∈ R*. Then,* P *is a projection along* ker E*, and* R *is a projection* *onto* im E*. If* E *is the Moore-Penrose inverse of* E*, in other words* E = E*, then* *these projections are orthogonal projections.* *ii) Conversely, let* P ∈ R
n×n *be an arbitrary projection along* ker E*, and let* R ∈ R m×m *be an arbitrary projection onto* im E*. Then, there exists a uniquely dened* *generalized inverse* E − ∈ R n×m *such that*
P = E − E *and* R = EE − (A.3)
*holds. If* P *and* R *are both orthogonal projections, then* E − *is the Moore-Penrose* *inverse. In other words:* E − = E + *.*
The denitions and propositions above relate generalized inverses and projections. The following denitions and lemmas add factorizations to our triumvirate. They can be found in the monograph by Lamour, März, and Tischendorf [72].
First, let us introduce the notion of well-matched factors.
**Denition A.6.** Let E ∈ R n×n be a given matrix. Two matrices A ∈ R n×m and D∈R m×n are called *well-matched factors of* E if E = AD holds, and A and D fulll the transversality condition
R m = ker A ⊕ im D. (A.4)
If in addition m = rank E holds, A and D are called *well-matched full-rank factors* *of* E.
The next lemma provides dierent conditions two matrices A and D may fulll that are equivalent to the transversality condition (A.4). Afterwards, we use this equivalency to construct well-matched factors. We conclude by showing that also well-matched full-rank factors can always be constructed for any given square matrix E, and that this particular factorization brings about some important consequences.
**Lemma A.7.** *Let two matrices* A∈R n×m *and* D∈R m×n *be given. Then, the* *following assertions are equivalent:*
*i)* rank AD = rank A = rank D*;* *ii)* im AD = im A *and* ker D = ker AD*;*
*iii)* R m = ker A ⊕ im D*.*
**Proof.** i) ⇐⇒ ii): Obviously, im AD ⊆ im A and ker D ⊆ ker AD hold. Thus,
im AD = im A ⇐⇒ rank AD = rank A. (A.5)
Since dim ker D = n − rank D = n − rank AD = dim ker AD, we also have
ker D = ker AD ⇐⇒ rank D = rank AD. (A.6)
i) and ii) =⇒ iii): We directly have m = dim ker A + rank D. Let y ∈ ker A ∩ im D. Then, there exists x ∈ R
n with Dx = y. Since ADx = Ay = 0, also x ∈ ker AD = ker D. This implies y = Dx = 0.
iii) =⇒ i): Immediately, rank D = rank A holds. Let x ∈ ker AD, i. e. ADx = 0. Then, Dx ∈ ker A ∩ im D, therefore Dx = 0 and further x ∈ ker D. We conclude that ker D = ker AD which is equivalent to rank D = rank AD (see above).
**Lemma A.8.** *For any given matrix* E∈R n×n *, there exists always a factorization* E = AD *where* A∈R n×m *and* D∈R m×n *with* m ≤ n *such that* rank A = rank E = rank D *holds.*
<u>A Generalized Inverses, Projections and Factorizations of Matrices</u>
**Proof.** We start from a given factorization E = AD˜ with A ∈ R n×m, D˜ ∈ R m×n, m ≤ n, such that im A = im E holds. For instance, simply take A = E and set D˜ correspondingly. Let A − be a generalized inverse of A and set D := A − AD˜. Then, we also have E = AD˜ = (AA −
A)D˜ = AD.
Furthermore, rank A = rank AD = rank D holds: The rst equality is clear as
rank AD = rank AD˜ = rank E = rank A.
As ker D ⊆ ker AD, we have rank A ≤ rank D by means of
rank A = rank AD = n − dim ker AD ≤ n − dim ker D = rank D.
Conversely, we have ker A ⊆ ker A − A⊆R m and im D = im A − AD˜ ⊆ im A − A⊆R m
##### by denition of D, thus
rank A ≥ rank A − A ≥ rank D.
**Remark.** The last two lemmas show that, given any matrix E ∈ R n×n, we may always construct a factorization that fullls the transversality condition (A.4). In particular, the initial choices of D˜ and A − in the proof of Lemma A.8 do not matter.
**Lemma A.9.** *For any square matrix* E∈R n×n *there exists a well-matched full-rank* *factorization.*
**Proof.** Any matrix E ∈ R n×n allows for a compact singular-value decomposition: Let r := rank E. There are matrices Ur,Vr∈ R n×r with orthonormal columns, and a diagonal matrix Σ = diag(σ₁,...,σr)∈R r×r containing the strictly positive singular values of E such that E=UrΣVrT.
With A := UrΣ∈R n×r and D := VrT∈ R r×n, it holds E = AD. By construction, we have r = rank A = rank D = rank E which is equivalent to the transversality condition (A.4) by Lemma A.7.
|||n×r||r×n|
|---|---|---|---|---|
|n×r|||−|r×n|
|−|R −|−|T|− T|
**Lemma A.10.** *Let* A ∈ R *and* D ∈ R *be two matrices with* rank A = rank D = r*. Furthermore, let* A ∈ R *be a generalized inverse of* A*, and let* D − ∈ R *be a generalized inverse of* D*. Then, it holds:*
*i)* A A = id r = DD*;* *ii)* {0} = ker A ∩ im A = ker A ∩ im(A) = ker D ∩ im D
− *.*
||−|r×r|
|r×r||r|
|−|−||
**Proof.** i) By Proposition A.5, DD ∈ R is a projection onto im D and A − A ∈ R is a projection along ker A. But im D = R and ker A = {0}, in other words DD is surjective, and A A is injective. The only projection that is injective or surjective is the identity.
||||T|− T||
|---|---|---|---|---|---|
|T|− T|n|T|||
|− T|||T − T|−|T|
||− T|||||
ii) We prove the equality {0} = ker A ∩ im(A). The rest follows analogously.
Let y ∈ ker A ∩ im(A) ⊂ R. Then, A y = 0 holds, and there exists an x ∈ R r
such that (A) x = y. Thus, 0 = A (A) x = (A A) x = A − Ax by i), whence also x = 0. Thus, y = (A) x = 0.
**Remark.** The well-matched full-rank factorization of E is not unique. Given well- matched full-rank factors A ∈ R n×r and D ∈ R r×n, any invertible matrix T ∈ R r×r
can be used to dene a new factorization: Set A˜ := AT and D˜ := T −1 D and observe that E = A˜ D˜ is, again, a well-matched full-rank factorization.
Notice how Lemma A.10 applies in particular to well-matched full-rank factors of a given square matrix E ∈ R n×n.
#### B Tools from Functional Analysis
In this chapter, we compile analytical tools and some of the denitions and assertions from the theory of functional analysis which we used most throughout this thesis. It is our intention to make for a consistent and self-contained lecture. However, we act under the assumption that vast majority of the statements given below are well-established. In each section, we refer to relevant literature.
We begin with some elementary inequalities; cf. [39, pp. 269 sqq., 103, pp. 42 sq.].
*Elementary Inequalities* Let a,b ∈ R be two numbers. Then,
(a + b) 2 ≤ 2a² + 2b² (B.1)
holds. For p ∈ (0, 1), the function f (x) = x p is subadditive. In particular, it holds for non-negative numbers a ≥ 0 and b ≥ 0 1 /2 1/2 1/2 (a + b) ≤ a + b. (B.2)
*Young’s Inequality* Let a ≥ 0 and b ≥ 0 be two non-negative real numbers, and let p,q > 1 be real numbers with p <u>1</u> + <u>1</u> q = 1. Then,
<u>a</u> p <u>b</u> q ab ≤ +. (B.3) p q This inequality can be adapted by inserting an ε > 0 to the very useful alternative
p<u>a</u> p <u>1 b</u> q ab ≤ ε + q. (B.4) p ε q
*Hölder’s Inequality and Minkowski’s Inequality (Bochner Space Versions)* Let (X, ‖·‖X) be a real Banach space with dual space (X ′, ‖·‖X′). Let 1 ≤ p,q ≤ ∞ be given such that p 1 + 1 q = 1 with the usual convention ∞ 1 = 0.
Let two functions f ∈ L p (0,T; X) and g ∈ L q (0,T; X ′ ) be given. The Hölder’s inequality reads ∣∫ ∣ ∫ ∣ T ∣ T ∣ ∣ ∣ 〈g(t),f (t)〉Xdt∣ ≤ |〈g(t),f (t)〉X| dt ∣0∣0
|0|0||||
|---|---|---|---|---|
||T|X|L (0,T;X|) L (0,T;X)|
||0||||
∫ (B.5)
≤ ‖g(t)‖X′ ‖f (t)‖ dt ≤ ‖g‖ q ′ ‖f ‖ p.
##### <u>B Tools from Functional Analysis</u>
For f,g ∈ L p (0,T; X), the Minkowski’s inequality reads
‖f + g‖Lp(0,T;X)≤ ‖f ‖Lp(0,T;X)+ ‖g‖Lp(0,T;X). (B.6)
##### B.1 Facts from Functional Analysis
We begin with one of the most fundamental tools in mathematics. The version stated here is taken from [124, p. 181]; cf also [125, p. 17].
**Banach’s Fixed-Point Theorem B.1.** *Let* (X,d) *be a non-empty complete metric* *space, and let* f : X → X *be a contraction, i. e. there is a positive number* L < 1 *such that* d(f (x),f (y)) ≤ Ld(x,y)
*holds for all* x,y ∈ X*. Then,* f *admits a unique xed point satisfying* f (x) = x*.* *Moreover, for any* x₀ ∈ X*, the iteration dened recursively through*
##### xn+1:= f (xn)
*converges for* n → ∞ *to this xed point* x ∈ X*.*
From now on and for the remainder of this section, let (X, ‖·‖X) and (Y, ‖·‖Y) be real Banach spaces, and let X be reexive. In accordance with the remainder of this thesis, we denote the dual of X with X ′, and the dual pairing between X and X ′ is denoted with 〈·, ·〉X. Moreover, we denote with (H, (·, ·)) a real Hilbert space with inner product (·, ·).
The next denition is taken from [108, p. 191]; cf. [39, p. 205, 126, p. 416].
**Denition B.2.** The triple (X,H,X ′ ) is called a *Gelfand triple* if the embedding X ֒→ H is continuous and dense, and we have a *consistent structure*. This is to say that we identify H with its dual H ′ by means of Riesz’s Representation Theorem, and demand that 〈y,x〉X= (y,x)H
holds for all x ∈ X and y ∈ H.
**Lemma B.3.** *In the reexive Banach space* X*, any bounded sequence* (xk)⊂X *admits a weakly convergent subsequence.*
**Proof.** A proof is given in [124, 120 sq., Satz III.3.7].
<u>B.1 Facts from Functional Analysis</u>
**Lemma B.4.** *Let* A: X → Y *be a compact operator. Then, it holds for all* (x
(k) ) ⊂
X x
(k) ⇀ x ∗ =⇒ Ax
(k) → Ax ∗
∈ Y.
**Proof.** A proof can be found in [8, p. 332, 61, p. 26].
**Lemma B.5.** *In a real Hilbert space* H*, weak convergence and convergence of the* *norms implies strong convergence. In other words, if* (x
(k) )⊂H *is weakly convergent*
*with weak limit point* x ∗ ∈ H*, and in addition, we have* ‖x
(k) ‖H→ ‖x
∗ ‖H*, then* x
(k) → x *strongly.*
**Proof.** This is immediate as
‖x
(k) − x ∗ ‖ 2 H= (x
(k) − x ∗ ,x
(k) − x ∗ ) H= ‖x
(k) ‖ 2 H+ 2(x
(k) ,x ∗ ) H+ ‖x
∗ ‖ 2 H→ 0.
This result transfers to uniformly convex spaces; cf. [126, p. 257] and also [124, pp. 187, 209, 23, p. 76].
**Denition B.6.** We call a subset K ⊂ X *convex* if for all x₁,x₂ ∈ K and all λ ∈ [0, 1] we have λx₁ + (1 − λ)x₂ ∈ K.
Let K ⊂ X be a convex set. A functional J : K → R ∪ {+∞} is called *convex* if for all x₁,x₂ ∈ K and all λ ∈ [0, 1] it holds
J (λx₁ + (1 − λ)x₂) ≤ λJ (x₁) + (1 − λ)J (x₂). (B.7)
**Lemma B.7.** *Any continuous, convex, and proper functional* J:X→R ∪ {+∞} *is* *weakly lower semicontinuous, i. e.*
x
(k) ⇀ x ∗ =⇒ lim inf J (x
(k) ) ≥ J (x ∗
). k→∞
*Here, the functional* J *is called* proper *if there is some* x ∈ X *with* J (x) < ∞*; see* *[14, p. 74].*
**Proof.** A proof can be found in [124, p. 138]; cf. also [61, pp. 25 sq.].
**Lemma B.8.** *Let* K ⊂ X *be a closed and convex subset. Then, the following* *assertions hold.*
*i) The set* K *is weakly sequentially closed, i. e. if* (x
(k) )⊂K *is a weakly convergent*
*sequence with weak limit point* x ∗ *, then* x ∗ ∈ K*.*
##### <u>B Tools from Functional Analysis</u>
*ii) If* K *is also bounded, then* K *is weakly sequentially compact. In other words,* *every sequence* (x
(k) )⊂K *contains a weakly convergent subsequence* (x
(kl) ) ⊂ x
(k) *with*
x (kl) ⇀ x ∗ ∈ K.
**Proof.** A proof can be found in [124, p. 121]; cf. also [61, p. 25].
##### B.2 On Sobolev Spaces
In this section, we collect some statements on Sobolev spaces. We refer especially to the textbooks by [1, 14, 23, 39, 44]. We recall the denition of a weak derivative; for simplicity in the one-dimensional case: Let I ⊂ R be an open, connected set, and let 1 ≤ p ≤ ∞ be given. Then, a function u ∈ L p
(I) is weakly dierentiable if a
function v ∈ L p
(I) exists such that
∫ ∫ uϕ ′ dx = − vϕ dx I I
holds for all ϕ ∈ Cc1(I). If such a function v exists, it is called the *weak derivative of*
u. In the denition, Cc1(I) denotes the set of all continuously dierentiable functions with compact support, where the support of ϕ is dened through
({ }) supp ϕ := clos x ∈ I, ϕ(x) 6= 0 ⊂ clos(I).
The Sobolev space of weakly dierentiable functions in L p
(I) is denoted by W
1,p
(I).
This denition can be translated to weak derivatives of higher order and higher- dimensional domains Ω ⊂ R d. The corresponding versions can be found in the references above. Note that Sobolev spaces can also be dened as the completion of the space of classically dierentiable functions with respect to a certain Sobolev norm. This is due to the famous Theorem by Meyers and Serrin B.9, published in a 1964 article bearing the perhaps shortest title in the history of mathematics. For more details and background information, in particular the denition of the Sobolev norms ‖·‖Wm,p(Ω), we refer to [1, pp. 59 sqq.].
##### Theorem by Meyers and Serrin B.9.
{ *Let* Ω⊂R d *be a domain.* } *Let* H m,p
(Ω) *be the*
*completion of the space* u ∈ C m
(Ω), ‖u‖Wm,p(Ω)< ∞*. Then, this space coincides*
*with the Sobolev space* W m,p
(Ω)*.*
**Proof.** A proof can be found in [1, p. 67].
<u>B.2 On Sobolev Spaces</u>
**Denition B.10.** Let Ω ⊂ R d be an open and bounded subset. The boundary ∂Ω is said to be *Lipschitz* if for each point x¯ ∈ ∂Ω, there exists r > 0 and a Lipschitz continuous mapping γ : R n−1 → R such that, upon rotating and relabeling the coordinate axes if necessary, we have { d } Ω ⊂ B(x¯,r) = x ∈ R, γ(x₁,...,xd−1) < xd∩ B(x¯,r)
{ d } where B(x¯,r) := x ∈ R, |xi− x¯i| < r for i = 1,...,d is the open ball with radius r around x¯.
A domain with Lipschitz boundary is called a *Lipschitz domain*.
**Remark.** This means that in a neighborhood of any boundary point x¯ ∈ ∂Ω, the boundary can be written as the graph of a Lipschitz continuous function. Moreover, Denition B.10 implies that Ω lies on one side of the boundary. Since Lipschitz continuous functions are dierentiable almost everywhere by Rademacher’s Theo- rem, Lipschitz domains allow for the denition of the outer unit normal ν(x¯) for almost all x¯ ∈ ∂Ω. Here, “almost all” has to be understood with respect to the (n − 1)-dimensional Hausdor measure. For more information, see in particular [44, pp. 150 sq.].
**Poincaré Inequality** The Poincaré inequality is one of the most important inequali- ties in the theory of Sobolev functions and consequently the modern theory of partial dierential equations. The following theorem is taken from [108, pp. 76 sq.].
**Theorem B.11.** *Let* Ω⊂R d *be a Lipschitz domain, let* 1 ≤ p < ∞ *be xed, and let* V ⊂ W 1,p
(Ω) *be a subset fullling one of the following conditions:*
*i) For all* u ∈ V*, it holds* u = 0 *on* ∂Ω*.*
∫ *ii) For all* u ∈ V*, it holds that* Ω u = 0*.*
*Then there exists a constant* CP> 0 *depending on* Ω *and* V *such that*
‖u‖W1,p(Ω)≤ CP‖∇u‖Lp(Ω)(B.8)
*holds for all* u ∈ V*. We call* CP*the Poincaré constant.*
*In the special case* p = 2 *and* V = H₀₁(Ω)*, this implies*
##### ‖u‖L2(Ω)≤ CP‖∇u‖L2(Ω). (B.9)
*This result can be transferred to hold in Sobolev-Bochner spaces, too. This can be* *seen from the proof given in [108, pp. 76 sq.].*
##### <u>B Tools from Functional Analysis</u>
**Green’s Identity** The following statement is formulated for classically dierentiable functions, but since we use it in Chapter 3 in the context of weak solutions to partial dierential equations, we state it here anyway. The assertion is taken from [23,
p. 296]. **Lemma B.12.** *Let* Ω⊂R
d *be a Lipschitz domain. For all* v ∈ C²(Ω) *and* w ∈ C¹(Ω)*,* *it holds* ∫ ∫ ∫ <u>∂v</u> (∆v)w dx = w dσ − ∇v · ∇w dx (B.10) Ω ∂Ω∂νΩ
##### B.3 On Bochner Spaces
In this section, we recall the notion of Bochner functions. For this compilation, we rely mainly on the textbooks by Emmrich [39, Chapters 7 and 8] and Růz̉ic̉ka [103, Chapter 2]. Further information can be found for instance in the books by Lions and Magenes [83, 84] and Zeidler [126, 127].
Throughout this section, let [0,T] ⊂ R be a nite time interval with T > 0 as in Assumption 1, let (X, ‖·‖X) be a real Banach space, and denote with (X ′, ‖·‖X′) its dual space.
##### B.3.1 Bochner Measurability and Bochner Integrability
**Denition B.13.** An abstract function u : [0,T] → X is called a *simple function* if there is a number n ∈ N such that u takes the form
∑ n u(t) = χBixi, i=1
where xi∈ X and Bi⊂ [0,T] holds for 1 ≤ i ≤ n, and the Biare Lebesgue measurable subsets with Bi∩ Bj= ∅ for i 6= j. The characteristic function χB corresponding to a set B ⊂ [0,T] is dened as { 0, t ∈/ B, χB(t) := 1, t ∈ B.
For a simple function u, we dene the *Bochner integral* as ∫
|T|n||
|||i i|
|0|i=1||
∑ u(t) dt := µ(B)x,
where µ(B) denotes the Lebesgue measure of B. Note that the integral is an element of X.
<u>B.3 On Bochner Spaces</u>
The denition can be extended to unbounded sets S ⊂ R; see [103, pp. 33 sqq.] for more information.
**Denition B.14.** An abstract function u : [0,T] → X is called *Bochner measurable* if there is a sequence of simple functions (u
(k) ) such that
u
(k)
(t) → u(t)
strongly in X for almost all t ∈ [0,T].
**Lemma B.15.** *If an abstract function* u : [0,T] → X *is Bochner measurable, then* *the function* t 7→ ‖u(t)‖X: [0,T] → R
##### is Lebesgue measurable.
**Proof.** A proof can be found in [39, pp. 154 sq.].
**Denition B.16.** Let u : [0,T] → X be a Bochner measurable function, and let (u
(k) )
be the sequence of simple functions from Denition B.14. Then, we call u *Bochner* *integrable* if for all ε > 0 there is some N ∈ N such that for all k,j ≥ N it holds ∫T ‖u
(k)
(t) − u
(j)
(t)‖ dt < ε.
If B ⊂ [0,T] is Lebesgue measurable, we dene the *Bochner integral of* u *on* B as ∫ ∫T u(t) dt := lim u
(k)
(t)χB(t) dt.
B n→∞ 0
Again, the integral is an element of X. This denition is independent of the choice of the sequence of simple functions; cf. [39, p. 155].
**Theorem B.17.** *Let* u : [0,T] → X *be a Bochner measurable function.*
*i) The abstract function* u *is Bochner integrable if and only if the mapping*
##### t 7→ ‖u(t)‖X: [0,T] → R
##### is Lebesgue integrable.
*ii) Let* u : [0,T] → X *be Bochner integrable. Then,* ∥∫ ∥ ∫ ∥ ∥ ∥ u(t) dt∥ ≤ ‖u(t)‖ Xdt ∥ ∥ B X B
##### <u>B Tools from Functional Analysis</u>
*holds for any Lebesgue measurable set* B ⊂ [0,T]*. Moreover, we have for all* u ∗ ∈ X ′
〈 ∫ 〉 ∫ u ∗, u(t) dt = 〈u ∗ ,u(t)〉Xdt. B X B
*iii) Let* Y *be another Banach space, and let* A ∈ L(X,Y) *be a linear and bounded* *operator. Let* u *be Bochner integrable with values in* X*. Then, the abstract function*
t 7→ (Au)(t) := Au(t) : [0,T] → Y
*is Bochner integrable with values in* Y*, and it holds* ∫ ∫ A u(t) dt = Au(t) dt. B B
**Proof.** A proof is given in [39, pp. 156 sqq.].
Before introducing the Banach spaces that have become known as Bochner spaces, we present a denition for a specic type of continuity. It is closely connected to the dierentiability of abstract functions and strong solutions for evolution equations, and thus it plays a particular role for the analysis presented in Chapter 2.
**Denition B.18.** An abstract function u : [0,T] → X is called *absolutely continuous* if for all ε > 0 there is a δ > 0 such that for any nite set of disjoint partial intervals (a
(k) ,b
(k) ) ⊂ [0,T], 1 ≤ k ≤ n we have ∑ n
∑ n |b
(k) − a
(k) | < δ =⇒ ‖u(b
(k) ) − u(a
(k) )‖X< ε.
k=1 k=1
**Lemma B.19.** *Let* u : [0,T] → X *be a Bochner-integrable function. For xed* t₀ ∈ [0,T]*, the function* ∫t v(t) := u(s) ds, t₀ *dened for* t ∈ [0,T]*, is absolutely continuous and classically Fréchet dierentiable* *with* v ′
(t) = u(t) *at almost every* t ∈ [0,T]*. This is in particular true for all times*
t ∈ [0,T] *at which* u *is continuous.*
**Proof.** A proof is given in [39, pp. 160 sq.].
In a sense, this statement provides the absolute continuity of the Bochner integral. On the other hand, the absolute continuity of an abstract function implies, under reexivity assumptions, the Bochner integrability of its derivative; see [39, p. 161].
<u>B.3 On Bochner Spaces</u>
**Theorem B.20.** *Let* X *be reexive and let* u : [0,T] → X *be an absolutely continuous* *function. Then, for almost all* t ∈ (0,T)*, the classical derivative* u ′
(t) *exists, and* u
′
*is Bochner-integrable on* (0,T)*. For any xed* t₀ ∈ [0,T]*, it holds* ∫t u(t) = u(t₀) + u ′
(s) ds
t₀
##### with t ∈ [0,T].
The combination of Lemma B.19 and Theorem B.20 can be understood as a variant of the Fundamental Theorem of Calculus.
##### B.3.2 Bochner Spaces and their Properties
Finally, we may introduce the Banach spaces of abstract functions and collect the most important information; cf. [39, pp. 150 sq., 163 sq.]
**Denition B.21.** We denote with C([0,T]; X) the vector space of continuous abstract functions with values in X. Equipped with the norm
‖u‖C([0,T];X):= max ‖u(t)‖X, t∈[0,T]
it is a Banach space. The space of classically (Fréchet) dierentiable functions is denoted by C¹([0,T]; X). It is a Banach space when equipped with the norm ()
||′||
|C ([0,T];X)|X|X|
‖u‖ 1 := max ‖u(t)‖ + ‖u (t)‖. t∈[0,T]
This notion translates directly to higher order derivatives.
For 1 ≤ p < ∞, we denote with L p (0,T; X) the vector space of equivalence classes of Bochner integrable function u : [0,T] → X with ∫T p ‖u(t)‖ X < ∞. 0
As for Lebesgue spaces, we identify functions which coincide almost everywhere in [0,T]. With L ∞ (0,T; X) we denote the space of equivalence classes of essentially bounded Bochner integrable functions. Equipped with the norms () 1 /p   ∫T   ‖u(t)‖ p dt for 1 ≤ p < ∞, X ‖u‖Lp(0,T;X):= 0    ess sup‖u(t)‖Xfor p = ∞ t∈(0,T)
##### <u>B Tools from Functional Analysis</u>
##### these spaces are Banach spaces.
With L¹ loc (0,T; X) we denote the space of equivalence classes of functions which are Bochner integrable on every compact subset B ⊂ (0,T).
##### Theorem B.22. The following assertions hold.
*i) Let* X *be separable. Then,* C([0,T]; X) *is separable. For* 1 ≤ p < ∞ *also* L p (0; T; X) *is separable.* *ii) For* 1 ≤ p ≤ ∞*, we have the embedding* C([0,T]; X) ֒→ L
p (0,T; X)*. The embed-* *ding is dense in the case* 1 ≤ p < ∞*. In particular, any function* u ∈ C([0,T]; X) *is* *Bochner integrable.*
*iii) Let* 1 < p < ∞*, and let* X *be reexive. Then,* L p (0,T; X) *is reexive. For* 1 < q < ∞ *with* p <u>1</u> + <u>1</u> q = 1*, we have*
L p (0,T; X) ′∼ = L q (0,T; X ′ ).
*Moreover, it holds* L¹(0,T; X) ′∼ = L ∞ (0,T; X ′ )*.*
*iv) Let* H *be a Hilbert space with inner product* (·, ·)*. Then,* L²(0,T; H) *is a Hilbert* *space when equipped with the inner product* ∫T (u,v)L2(0,T;H):= (u(t),v(t))Hdt. 0
*v) Let* Y *be another Banach space. Then,* X ֒→ Y *implies* L
p (0,T; X) ֒→ L q (0,T; Y<u>)</u> *for all* 1 ≤ q ≤ p ≤ ∞*.*
##### B.3.3 Weak Dierentiability in Bochner Spaces
Next, we dene the notion of weak dierentiability for Bochner spaces analogously to the denition we gave for Sobolev spaces in Appendix B.2. An abstract function u ∈ L¹ loc (0,T; X) is called *weakly dierentiable* if a function v ∈ L¹ loc (0,T; X) exists such that ∫ ∫ T T u(t)ϕ ′
(t) dt = − v(t)ϕ(t) dt
0 0 holds for all ϕ ∈ Cc1(0,T). In contrast to Sobolev functions, this equation now holds in X. If such a function v exists, it is called the *weak derivative of* u.
**Lemma B.23.** *Let two functions* u,v ∈ L¹(0,T; X) *be given. Then, the following* *assertions are equivalent:*
*i)* v *is weak derivative of* u*, i. e.* v = u
′ *.*
<u>B.3 On Bochner Spaces</u>
*ii) There exists a* u₀ ∈ X *such that* ∫t u(t) = u₀ + v(s) ds (B.11) 0
*holds for almost all* t ∈ (0,T)*.*
**Proof.** A proof is given in [39, pp. 202 sqq.].
As before, we may introduce the space of weakly dierentiable abstract functions. For 1 ≤ p < ∞, we dene {} W 1,p (0,T; X) := v ∈ L p (0,T; X), ∃v ′ ∈ L p (0,T; X)
as the space of all Bochner-integrable functions that have a Bochner-integrable weak derivative of the same regularity. Equipped with the norm
‖u‖W1,p(0,T;X):= ‖u‖Lp(0,T;X)+ ‖u ′ ‖Lp(0,T;X),
the space W 1,p (0,T; X) is a Banach space; see [39, p. 204, 108, p. 186]. We have the following regularity result.
**Lemma B.24.** *Let* 1 ≤ p < ∞*. Any function* u ∈ W 1,p (0,T; X) *is almost everywhere* *equal to an absolutely continuous function on* [0,T]*, and the embedding*
W 1,p (0,T; X) ֒→ C([0,T]; X)
*is continuous.*
**Remark.** Let u ∈ W 1,1 (0,T; X). Since functions that coincide almost everywhere are equal in the sense of L¹(0,T; X), we may always choose the absolutely continuous representative and evaluate u at t₀. Then, Equation (B.11) from above reads ∫t u(t) = u(0) + v(s) ds 0
and holds for almost all t ∈ [0,T]. We also refer to the trace theorem for Bochner functions stated in [108, p. 187].
Finally, we introduce and shortly discuss a rather specic function space which we used in Chapter 4. Recall in particular the remark on page 59. The function space is related to other spaces which appear commonly in the discussion of second order hyperbolic partial dierential equations; see e. g. [83, pp. 265 sqq., 108, pp. 227 sqq.].
##### <u>B Tools from Functional Analysis</u>
Let (X,H,X ′ ) be a Gelfand triple, see Denition B.2. We dene the function space {} V := v ∈ L²(0,T; X), v ′ ∈ L²(0,T; H).
This denition is comparable to the space W (0,T) for parabolic problems, see e. g. [39, pp. 206 sq.], but requires a higher spatial regularity for the rst time derivative. Equipped with the norm
||′|
|---|---|
|L (0,T;X)|L (0,T;H)|
‖v‖V:= ‖v‖ 2 + ‖v ‖ 2, (B.12)
it is a Banach space. The following assertions hold.
**Lemma B.25.** *Any function* v ∈ V *is almost everywhere equal to a continuous* *function* v˜ ∈ C([0,T]; H)*, and the embedding*
##### V ֒→ C([0,T]; H) (B.13)
*is continuous. For* v,w ∈ V*, the rule of partial integration* ∫t 2 (v ′
(s),w(s))H+ (v(s),w
′
(s))Hds = (v(t₂),w(t₂))H− (v(t₁),w(t₁))H(B.14)
t₁
*holds for* 0 ≤ t₁ ≤ t₂ ≤ T*. Moreover, the embedding* C ∞ ([0,T]; X) ֒→ V *is dense.*
**Proof.** Due to the embedding H ֒→ X ′, the continuous embedding V ֒→ C([0,T]; H) and the density of C ∞ ([0,T]; X) follow directly from [39, pp. 206 sqq.]. The rule of partial integration in [39, p. 207] reads ∫t 2 ′
|〈v|(s),w(s)〉|+ 〈v(s),w|(s)〉|ds = (v(t₂),w(t₂))|− (v(t₁),w(t₁))||
|---|---|---|---|---|---|---|
|t₁||X||X|H|H|
|||||||′|
|′|||||||
|′|X|′|H||′ X|′ H|
X ′ X H H t₁
for 0 ≤ t₁ ≤ t₂ ≤ T. But due to the higher regularity of the time derivatives v and w, the consistent structure of the Gelfand triple implies
〈v (s),w(s)〉 = (v (s),w(s)) as well as 〈v(s),w (s)〉 = (v(s),w (s)).
The rule of partial integration (B.14) follows immediately.
The next result also exists in a similar version for the space W (0,T). We translated it from [39, pp. 185 sq., 211 sq.].
**Lemma B.26.** *Let* u ∈ C¹([0,T]; H)*. Then,*
<u>1 d</u>2 ′ ‖u(t)‖H= (u (t),u(t))H(B.15) 2 dt
<u>B.3 On Bochner Spaces</u>
*holds for all* t ∈ [0,T]*. This result can be generalized: For* v ∈ V*, we have*
<u>1 d</u>2 ′ ‖u(t)‖H= (u (t),u(t))H(B.16) 2 dt
##### for almost all t ∈ (0,T).
**Proof.** The rst assertion is given in [39, pp. 185 sq.]. The second assertion follows from [39, pp. 211 sq.] due to the higher regularity of v ∈ V and the consistent structure of the Gelfand triple.
#### C On Abstract Dierential Equations and Operator Equations
In this appendix, we recapitulate some existence results for abstract dierential equa- tions and operator equations. This includes in particular the Generalized Picard- Lindelöf Theorem C.3 and Theorem by Browder and Minty C.9. We also present a denition of Nemytskii operators and some properties of these operators.
This composition is based on the textbooks by Emmrich [39], Růz̉ic̉ka [103], Werner [124], and Zeidler [125–127] and the 1992 article on Nemytskii operators in Bochner spaces by Goldberg, Kampowsky, and Tröltzsch [48]. We would also like to refer to the standard textbook on the semigroup approach for abstract ODEs by Pazy [95].
Throughout this appendix, let [0,T] ⊂ R be a nite time interval with T > 0, let (X, ‖·‖X), (Y, ‖·‖Y), and (Z, ‖·‖Z) be a real Banach spaces.
##### C.1 Tools from Abstract ODE Theory
##### Consider the initial value problem
u ′
(t) = f (t,u(t)) with u(0) = u₀, (C.1)
where the abstract ODE (C.1) is supposed to hold in X for almost all t ∈ [0,T]. The right-hand side function f : [0,T] × X → X is xed. Given some initial data u₀ ∈ X, we look for Banach space valued functions u : [0,T] → X that solve (C.1).
The following denition is taken from [125, pp. 79 sqq.].
**Denition C.1.** A continuous mapping f : [0,T] × X → Y is said to be *locally* *Lipschitz continuous with respect to the second variable* if for all t₀ ∈ [0,T] and all x₀ ∈ X, there are positive numbers c₁,c₂ > 0 and a constant L(c₁,c₂)≥0 such that the estimation ‖f (t,x₁) − f (t,x₂)‖Y≤ L(c₁,c₂)‖x₁ − x₂‖X(C.2)
holds for all t ∈ [0{,T] with |t − t₀| ≤ c₁, as } well as for all x₁,x₂ ∈ B(x₀,c₂)⊂X where B(x₀,c₂) := x ∈ X, ‖x − x₀‖X≤ c₂ is the closed ball with radius c₂ around x₀.
<u>C On Abstract Dierential Equations and Operator Equations</u>
For completeness, we would like to restate Lemma 2.23 of Chapter 2. It is a rather general auxiliary result which ts quite well into the framework of this section. The proof is given at the end of Section 2.4 on pages 34 to 35.
**Lemma C.2.** *Let* f : [0,T] × X → Y *and* g : [0,T] × Y → Z *be two continuous* *mappings which are locally Lipschitz continuous with respect to their respective* *second variables. Then, the composition* g ◦ f : [0,T] × X → Z *given by*
(g ◦ f)(t,x) := g(t,f (t,x)) *for* t ∈ [0,T] *and* x ∈ X (C.3)
*is locally Lipschitz continuous with respect to its second variable, i. e. for all* t₀ ∈ [0,T] *and* x₀ ∈ X *there are positive numbers* c₁,c₂ > 0 *and a constant* L(c₁,c₂)≥0 *such that* ‖g(t,f (t,x₁)) − g(t,f (t,x₂))‖Z≤ L(c₁,c₂)‖x₁ − x₂‖X
*holds for all* t ∈ [0,T] *with* |t − t₀| ≤ c₁*, as well as for all* x₁,x₂ ∈ B(x₀,c₂)⊂X*.*
**Generalized Picard-Lindelöf Theorem C.3.** *Let* f : [0,T] × X → X *be a continuous* *mapping that is locally Lipschitz continuous with respect to the second variable in* *the sense of Denition C.1. Assume moreover that there is a constant* K≥0 *such* *that* ‖f (t,u(t))‖X≤ K
*holds for all* t ∈ [0,T] *for which a solution* u : [0,T] → X *to the initial value problem* (C.1) *exists.*
*Then, for any xed initial value* u₀ ∈ X*, the initial value problem* (C.1) *admits a* *unique continuously dierentiable solution* u : [0,T] → X*.*
**Proof.** This result is proved in this form in [125, pp. 80 sq.].
We conclude this section by stating one of the most widely used tools in ODE theory. This following version is taken from [39, p. 180].
**Gronwall’s Lemma C.4.** *Let* T > 0 *and* t₀ ∈ [0,T) *be given. Let* a,b ∈ L ∞ (t₀,T) *be* *two functions, and let* λ ∈ L¹(t₀,T) *with* λ(t) ≥ 0 *for almost all* t ∈ (t₀,T)*. Assume* *that the estimation* ∫t a(t) ≤ b(t) + λ(s)a(s) ds t₀
*is fullled for almost all* t ∈ (t₀,T)*. Then, for almost all* t ∈ (t₀,T) *it holds* ∫t a(t) ≤ b(t) + e Λ(t)−Λ(s) λ(s)b(s) ds, t₀
<u>C.2 Nemytskii Operators on Bochner Spaces</u>
∫t *where* Λ(t) := t λ(τ) dτ*.* 0 *If* b *is monotone increasing and continuous, then*
a(t) ≤ e Λ(t) b(t)
*holds.*
**Proof.** A proof can be found in [39, pp. 180 sq.].
##### C.2 Nemytskii Operators on Bochner Spaces
The following statements are all taken from Goldberg, Kampowsky, and Tröltzsch [48]. Recall the notion of Bochner integrable functions, Denition B.16, from Ap- pendix B.3.
The idea of Nemytskii operators is to associate to mappings f : [0,T] × X → Y certain operators between function spaces through
##### [F (u)](t) := f (t,u(t)). (C.4)
In other words, the operator F assigns to the abstract function u : [0,T] → X an abstract function v : [0,T] → Y with v(t) := f (t,u(t)). The analysis of Nemytskii op- erators deals with necessary and sucient conditions for continuity, dierentiability, and more.
**Denition C.5.** A mapping f : [0,T] × X → Y fullls the *Carathéodory condition* if for any xed x ∈ X the mapping t 7→ f (t,x) : [0,T] → Y is Bochner-measurable, and for almost all t ∈ [0,T], the mapping x 7→ f (t,x) : X → Y is continuous.
**Denition C.6.** Let 1 ≤ p,q < ∞ be xed. A mapping f : [0,T] × X → Y fullls the *growth condition* if there is some β ≥ 0 and a function γ ∈ L q (0,T) such that
p /q ‖f (t,x)‖Y≤ γ(t) + β‖x‖ X (C.5)
holds for almost all t ∈ [0,T] and x ∈ X.
**Theorem C.7.** *Let* f : [0,T] × X → Y *fulll the Carathéodory condition. If, in* *addition, it fullls the growth condition* (C.5) *for* 1 ≤ p,q < ∞*, then the cor-* *responding Nemytskii operator* F *dened through* (C.4) *is a continuous mapping* F:L p (0,T; X) → L q (0,T; Y)*.*
*Proof.* This theorem is partially proved in [48, pp. 128, 132].
<u>C On Abstract Dierential Equations and Operator Equations</u>
##### C.3 On Monotone Operators
The following statements are taken from [103, Chapter 3, 127, Chapters 25 and 26].
In this section, let (X, ‖·‖X) be a real reexive Banach space with dual (X ′, ‖·‖X′). We denote the dual pairing through 〈·, ·〉X. Let (H, (·, ·)) be a real Hilbert space.
**Denition C.8.** i) An operator A : X → X ′ is said to be *monotone* if for all x₁,x₂ ∈ X
##### 〈Ax₁ − Ax₂,x₁ − x₂〉X≥ 0
holds.
ii) A monotone operator A is said to be *strictly monotone* if we have for all x₁ 6= x₂
##### 〈Ax₁ − Ax₂,x₁ − x₂〉X> 0.
iii) An operator A : X → X ′ is called *coercive* if for all x ∈ X it holds
<u>〈Ax,x〉X</u> lim → +∞. ∥x∥X→∞ ‖x‖X
iv) An operator A : X → X ′ is called *strongly monotone* if there is a µ > 0 such that for all x₁,x₂ ∈ X, we have
〈Ax₁ − Ax₂,x₁ − x₂〉X≥ µ‖x₁ − x₂‖ 2
X.
v) An operator A : X → X
′ is said to be *demicontinuous* if
|(k)|(k)|∗||
|---|---|---|---|
|(k)||||
|′||||
|||X||
x → x ∗ =⇒ Ax ⇀ Ax
holds for any sequence (x) ⊂ X.
vi) An operator A : X → X is said to be *hemicontinuous* if the real function
##### t 7→ 〈A(x₁ + tx₂),x₃〉
is continuous on [0, 1] for all x₁,x₂,x₃ ∈ X.
**Remark.** Strictly monotone operators are clearly monotone; moreover, strongly monotone operators are strictly monotone and coercive. Strong monotonicity im- plies ‖Ax₁ − Ax₂‖X′ ≥ µ‖x₁ − x₂‖X. (C.6)
Cf. [127, pp. 501 sq.] for more information.
<u>C.3 On Monotone Operators</u>
**Theorem by Browder and Minty C.9.** *Let* X *be a separable reexive Banach space,* *and let* A: X → X ′ *be a monotone, coercive, and hemicontinuous operator. Then,* A *is surjective. Thus, for any* b ∈ X ′ *there exists a solution* u ∈ X *to the operator* *equation* Au = b. (C.7)
*The set of all solutions to this equation is closed, bounded, and convex.*
*If* A *is strictly monotone, the solution to* (C.7) *is unique. Moreover, the strict* *monotonicity of* A *implies the existence of an inverse operator* A −1 : X ′ → X *which* *is strictly monotone, demicontinuous, and bounded. Recall that bounded operators* *map bounded sets into bounded sets.*
*If* A *is strongly monotone, then* A −1 *is even Lipschitz continuous.*
*Proof.* A proof is given in [103, pp. 65 sqq.].
**Remark.** The Theorem by Browder and Minty C.9 holds also true in non-separable Banach spaces. This extension can be proved for instance by means of so-called Moore-Smith sequences, confer [125, pp. 758 sqq., 127, pp. 561 sq.], or by using a cut-o technique to compensate for the lack of a countable basis in a modied Galerkin approach as in [103, pp. 68, 132 sqq.].
The following result can be found in literature as the Zarantonello’s Theorem. It appeared prior to the Browder-Minty Theorem stated above and follows directly from it. Confer [127, pp. 503 sqq.].
**Zarantonello’s Theorem C.10.** *Let* A: H → H ′ *be a strongly monotone and Lip-* *schitz continuous operator. Then, for each* b ∈ H ′ *, the operator equation* (C.7) *has a unique solution* u ∈ H*. The inverse operator* A −1 : H ′ → H *is Lipschitz* *continuous.*
#### Bibliography
[1] Robert Alexander Adams and John James Francis Fournier. *Sobolev Spaces*. 2nd ed. Vol. 140. Pure and Applied Mathematics. Academic Press, 2003. ISBN: 978-0-120-44143-3. [2] Giuseppe Alì, Andreas Bartel, and Michael Günther. “Existence and Unique- ness for an Elliptic PDAE Model of Integrated Circuits.” In: *SIAM Journal on* *Applied Mathematics* 70.5 (2010), pp. 1587–1610. DOI: 10.1137/070702138. [3] Giuseppe Alì, Andreas Bartel, and Michael Günther. “Parabolic Dierential- Algebraic Models in Electrical Network Design.” In: *Multiscale Modeling &* *Simulation* 4.3 (2003), pp. 813–838. DOI: 10.1137/040610696. [4] Giuseppe Alì, Andreas Bartel, Michael Günther, and Caren Tischendorf. “El- liptic Partial Dierential-Algebraic Multiphysics Models in Electrical Net- work Design.” In: *Mathematical Models and Methods in Applied Sciences*
13.9 (2003), pp. 1261–1278. DOI: 10.1142/s0218202503002908.
[5] Giuseppe Alì, Andreas Bartel, and Nella Rotundo. “An Existence Result for Index-2 PDAE System Arising in Semiconductor Modeling.” In: *Progress in* *Industrial Mathematics at ECMI 2010*. Ed. by Michael Günther et al. Berlin, Heidelberg: Springer, 2012, pp. 45–51. ISBN: 978-3-642-25100-9. [6] Giuseppe Alì, Giovanni Mascali, and Roland Pulch. “Hyperbolic PDAEs for Semiconductor Devices Coupled with Circuits.” In: *Scientic Computing in* *Electrical Engineering SCEE 2008*. Ed. by Janne Roos and Luis R. J. Costa. Berlin, Heidelberg: Springer, 2010, pp. 305–312. ISBN: 978-3-642-12294-1. [7] Serge Alinhac. *Blowup for Nonlinear Hyperbolic Equations*. Progress in Non- linear Dierential Equations and Their Applications. Boston: Birkhäuser,
1995. ISBN: 978-1-461-27588-6. DOI: 10.1007/978-1-4612-2578-2.
[8] Hans Wilhlem Alt. *Lineare Funktionalanalysis*. 6., überarbeitete Auage. Berlin: Springer, 2012. ISBN: 978-3-642-22260-3. [9] Robert Altmann. “Regularization and Simulation of Constrained Partial Dif- ferential Equations.” PhD thesis. Technische Universität Berlin, 2015. [10] Robert Altmann and Jan Heiland. “Regularization and Rothe Discretiza- tion of Semi-Explicit Operator DAEs.” In: *International Journal of Numerical* *Analysis and Modeling* 15.3 (2018), pp. 452–478. ISSN: 2617-8710. [11] Robert Altmann, Roland Maier, and Benjamin Unger. “Semi-explicit Dis- cretization Schemes for Weakly Coupled Elliptic-Parabolic Problems.” In: *Mathematics of Computation* 90.329 (2021). DOI: 10.1090/mcom/3608.
<u>Bibliography</u>
[12] Martin Arnold and Bernd Simeon. “Pantograph and Catenary Dynamics. A Benchmark Problem and its Numerical Solution.” In: *Applied Numerical* *Mathematics* 34.4 (2000), pp. 345–362. [13] Martin Arnold and Bernd Simeon. *The Simulation of Pantograph and Cate-* *nary. A PDAE Approach*. 1998. URL: https : / / www. mathematik. tu-darmstadt.de/media/mathematik/forschung/preprint/ps2pdf/1990.pdf (visited on 09/19/2023). [14] Hedy Attouch, Giuseppe Buttazzo, and Gérard Michaille. *Variational Analy-* *sis in Sobolev and BV spaces. Applications to PDEs and Optimization*. 2nd ed. Society for Industrial and Applied Mathematics and The Mathematical Pro- gramming Society, 2014. ISBN: 978-1-611973-47-1. [15] Katalin Balla and Roswitha März. “A Unied Approach to Linear Dierential Algebraic Equations and Their Adjoint Equations.” In: *Zeitschrift für Analysis* *und ihre Anwendungen* 21.3 (2002), pp. 783–802. DOI: 10.4171/zaa/1108. [16] Andreas Bartel and Michael Günther. “PDAEs in Rened Electrical Network Modeling.” In: *SIAM Review* 60.1 (2018), pp. 56–91. DOI: 10.1137/17m111
3643.
[17] Ben Ben-Israel and Thomas N. E. Greville. *Generalized Inverses. Theory and* *Applications*. 2nd ed. CMS Books in Mathematics. New York, Berlin: Sprin- ger, 2003. ISBN: 978-0-387-21634-8. DOI: 10.1007/b97366. [18] Lorenz T. Biegler, Stephen LaVern Campbell, and Volker Mehrmann. *Con-* *trol and Optimization with Dierential-Algebraic Constraints*. Advances in Design and Control. Philadelphia, PA: Society for Industrial and Applied Mathematics, 2012. DOI: 10.1137/9781611972252. [19] Raul Borsche, Rinaldo M. Colombo, and Mauro Garavello. “Mixed systems: ODEs – Balance laws.” In: *Journal of Dierential Equations* 252.3 (2012), pp. 2311–2338. ISSN: 0022-0396. DOI: 10.1016/j.jde.2011.08.051. [20] Raul Borsche, Rinaldo M. Colombo, and Mauro Garavello. “On the Coupling of Systems of Hyperbolic Conservation Laws with Ordinary Dierential Equa- tions.” In: *Nonlinearity* 23.11 (2010). DOI: 10.1088/0951-7715/23/11/002. [21] Kathryn Eleda Brenan, Stephen LaVern Campbell, and Linda Ruth Petzold. *Numerical Solution of Initial-Value Problems in Dierential-Algebraic Equa-* *tions*. Society for Industrial and Applied Mathematics, 1995. DOI: 10.1137/1
.9781611971224.
[22] Alberto Bressan. “Hyperbolic Conservation Laws. An Illustrated Tutorial.” In: *Modelling and Optimisation of Flows on Networks*. Ed. by Benedetto Piccoli and Michel Rascle. Lecture Notes in Mathematics 2062. Berlin: Springer, 2012, pp. 157–245. ISBN: 978-3-642-32160-3. DOI: 10.1007/978-3-642-32160-3. [23] Haim Brezis. *Functional Analysis, Sobolev Spaces and Partial Dierential* *Equations*. New York: Springer, 2011. ISBN: 978-0-387-70914-7. DOI: 10.100 7/978-0-387-70914-7.
<u>Bibliography</u>
[24] Nicolas Burq, Gilles Lebeau, and Fabrice Planchon. “Global Existence for Energy Critical Waves in 3-D Domains.” In: *Journal of the American Mathe-* *matical Society* 21.3 (2008), pp. 831–845. ISSN: 1088-6834. DOI: 10.1090/s0 894-0347-08-00596-1.
[25] Guido Buzzi-Ferraris and Flavio Manenti. *Dierential and Dierential-Alge-* *braic Systems for the Chemical Engineer. Solving Numerical Problems*. Wein- heim, Germany: Wiley-VCH, 2014. ISBN: 978-3-527-66713-0.
[26] Stephen LaVern Campbell and Carl D. Meyer. *Generalized Inverses of Linear* *Transformations*. Classics in Applied Mathematics 56. in particular Corollary
6.2.1. Society for Industrial and Applied Mathematics, 2009. ISBN: 978-0- 89871-904-8. DOI: 10.1137/1.9780898719048.
[27] Eduardo Casas. “Pontryagin’s Principle for State-Constrained Boundary Con- trol Problems of Semilinear Parabolic Equations.” In: *SIAM Journal on Con-* *trol and Optimization* 35.4 (1997), pp. 1297–1327. DOI: 10.1137/s03630129 95283637.
[28] Eduardo Casas, Juan Carlos De Los Reyes, and Fredi Tröltzsch. “Sucient Second-Order Optimality Conditions for Semilinear Control Problems with Pointwise State Constraints.” In: *SIAM Journal on Optimization* 19.2 (2008), pp. 616–643.
[29] Eduardo Casas and Fredi Tröltzsch. “Second Order Optimality Conditions and Their Role in PDE Control.” In: *Jahresbericht der Deutschen Mathema-* *tiker-Vereinigung* 117 (2015), pp. 3–44.
[30] Thierry Cazenave and Alain Haraux. *An Introduction to Semilinear Evolution* *Equations*. Trans. French by Yvan Martel. Revised Edition. Oxford Science Publications. Oxford: Clarendon Press, 1998. ISBN: 019850277x.
[31] Thierry Cazenave and Alain Haraux. “Équations d’Évolution avec Non-Li- néarité Logarithmique.” French. In: *Annales de la Faculté des Sciences de* *Toulouse: Mathématiques*. 5th ser. 2.1 (1980), pp. 21–51.
[32] Jean-Michel Coron. *Control and Nonlinearity*. Mathematical Surveys and Monographs 136. Providence, Rhode Island: American Mathematical Soci- ety, 2007. ISBN: 978-1-4704-1363-7. DOI: 10.1090/surv/136.
[33] Jean-Michel Coron and Georges Bastin. *Stability and Boundary Stabilization* *of 1-D Hyperbolic Systems*. Cham: Birkhäuser, 2016. ISBN: 978-3-319-32062-
5. DOI: 10.1007/978-3-319-32062-5.
[34] Sébastien Court and Karl Kunisch. *Design of the monodomain model by* *articial neural networks*. Version 2. 2021. arXiv: 2107.03136v2.
[35] Constantine Michael Dafermos. *Hyperbolic Conservation Laws in Continuum* *Physics*. Grundlehren der mathematischen Wissenschaften 325. Berlin: Sprin- ger, 2000. ISBN: 978-3-662-22021-4.
<u>Bibliography</u>
[36] Florent Di Meglio, Florent Bribiesca Argomedo, Long Hu, and Miroslav Krstic. “Stabilization of Coupled Linear Heterodirectional Hyperbolic PDE–ODE Systems.” In: *Automatica* 87 (2018), pp. 281–289. ISSN: 0005-1098. DOI: 10
.1016/j.automatica.2017.09.027.
[37] François Dubois, Nicolas Petit, and Pierre Rouchon. “Motion Planning and Nonlinear Simulations for a Tank Containing a Fluid.” In: *1999 European* *Control Conference (ECC)*. Ieee. 1999, pp. 3232–3237. DOI: 10.23919/ecc.1
999.7099825.
[38] Herbert Egger. “A Robust Conservative Mixed Finite Element Method for Isentropic Compressible Flow on Pipe Networks.” In: *SIAM Journal on Sci-* *entic Computing* 40.1 (2018), A108–a129. ISSN: 1064-8275. DOI: 10.1137 /16m1094373.
[39] Etienne Emmrich. *Gewöhnliche und Operator-Dierentialgleichungen. Eine* *integrierte Einführung in Randwertprobleme und Evolutionsgleichungen für* *Studierende*. German. Wiesbaden: Vieweg & Sohn Verlag, 2004. ISBN: 978- 3-528-03213-5.
[40] Etienne Emmrich and Volker Mehrmann. “Analysis of Operator Dierential- Algebraic Equations Arising in Fluid Dynamics.” In: *Computational Methods* *in Applied Mathematics* 13.4 (2013), pp. 443–470. DOI: doi:10.1515/cmam- 2013-0018.
[41] Diana Estévez Schwarz. “Consistent Initialization for Index-2 Dierential- Algebraic Equations and its Applications to Circuit Simulation.” PhD thesis. Berlin: Humboldt-Universität zu Berlin, 2000.
[42] Diana Estévez Schwarz and Caren Tischendorf. “Mathematical Problems in Circuit Simulation.” In: 7.2 (2001), pp. 215–223. DOI: 10.1076/mcmd.7.2.2
15.3647.
[43] Lawrence Craig Evans. *Partial Dierential Equations*. Graduate Studies in Mathematics 19. American Mathematical Society, 1998. ISBN: 978-0-821- 80772-9.
[44] Lawrence Craig Evans and Ronald F. Gariepy. *Measure Theory and Fine* *Properties of Functions*. Revised Edition. Textbooks in Mathematics. CRC Press, 2015. ISBN: 978-1-482-24238-6.
[45] Xiaodan Feng and Zhifei Zhang. “Output Feedback Stabilization for a Wave- ODE Cascade System with the Time-Varying Input and Output Delay.” In: *Results in Mathematics* 77.2 (2022). ISSN: 1422-6383. DOI: 10.1007/s00025 -022-01611-w.
[46] Richard P. Feynman, Robert B. Leighton, and Matthew Sands. *The Feyn-* *man Lectures on Physics*. Vol. 2: *Mainly Electromagnetism and Matter*. New Millenium Edition. New York: Basic Books, 2011. ISBN: 978-0-465-02494-0.
<u>Bibliography</u>
[47] Giovanni P. Galdi, Anne M. Robertson, Rolf Rannacher, and Stefan Turek. *Hemodynamical Flows. Modeling, Analysis and Simulation*. Oberwolfach Se- minars. Basel: Birkhäuser. ISBN: 978-3-764-37806-6. DOI: 10.1007/978-3-7 64-37806-6.
[48] Helmuth Goldberg, Winfried Kampowsky, and Fredi Tröltzsch. “On Nemyt- skij Operators in Lp-Spaces of Abstract Functions.” In: *Mathematische Nach-* *richten* 155.1 (1992), pp. 127–140. ISSN: 1522-2616. DOI: 10.1002/mana.19 921550110.
[49] Walter Greiner. *Relativistic Quantum Mechanics. Wave Equations*. 3rd ed. Berlin: Springer, 2000. ISBN: 978-3-540-67457-3.
[50] Dennis Groh and Caren Tischendorf. “Error analysis for Galerkin-BDF dis- cretizations of DAEs with elliptic operator constraints.” In: *Journal of Com-* *putational and Applied Mathematics* 422 (2023). ISSN: 0377-0427. DOI: 10
.1016/j.cam.2022.114946.
[51] Dietmar Gross, Werner Hauger, and Peter Wriggers. *Technische Mechanik*. Vol. 4: *Hydromechanik, Elemente der Höheren Mechanik, Numerische Meth-* *oden*. German. 11th ed. Berlin, Heidelberg: Springer Vieweg, 2023. ISBN: 978-3-662-66524-4. DOI: 10.1007/978-3-662-66524-4.
[52] Martin Gugat, Markus Dick, and Günter Leugering. “Gas Flow in Fan-Shaped Networks: Classical Solutions and Feedback Stabilization. Classical Solutions and Feedback Stabilization.” In: *SIAM Journal on Control and Optimization*
49.5 (2011), pp. 2101–2117. DOI: 10.1137/100799824.
[53] Martin Gugat and Stefan Ulbrich. “Lipschitz Solutions of Initial Boundary Value Problems for Balance Laws.” In: *Mathematical Models and Methods in* *Applied Sciences* 28.5 (2018), pp. 921–951. DOI: 10.1142/s02182025185002
40.
[54] Martin Gugat and Stefan Ulbrich. *On the Existence, Uniqueness and Ex-* *act Controllability of Lipschitz Solutions of Initial Boundary Value Problems* *for Gas Networks with Nonconstant Compressibility Factor*. URL: https : //www.academia.edu/download/95473409/ Sulb2017_5.pdf (visited on 09/25/2023).
[55] Phi Ha. “Analysis and Numerical Solutions of Delay Dierential-Algebraic Equations.” PhD thesis. Berlin: Technische Universität Berlin, 2015.
[56] Oliver Habeck. “Mixed-Integer Optimization with Ordinary Dierential Equa- tions for Gas Networks.” PhD thesis. Technische Universität Darstadt, 2020.
[57] Oliver Habeck, Marc E. Pfetsch, and Stefan Ulbrich. “Global Optimization of Mixed-Integer ODE Constrained Network Problems Using the Example of Stationary Gas Transport.” In: *SIAM Journal on Optimization* 29.4 (2019), pp. 2949–2985. DOI: 10.1137/17m1152668.
<u>Bibliography</u>
[58] Ernst Hairer, Christian Lubich, and Michael Roche. *The Numerical Solu-* *tion of Dierential-Algebraic Systems by Runge-Kutta Methods*. Vol. 1409. Lecture Notes in Mathematics. Berlin, Heidelberg: Springer, 1989. ISBN: 978- 3-540-46832-5. DOI: 10.1007/BFb0093947.
[59] Ernst Hairer and Gerhard Wanner. *Solving Ordinary Dierential Equations.* *Sti and Dierential-Algebraic Problems*. Second Revised edition. Vol. 2. Springer Series in Computational Mathematics 14. Berlin: Springer, 1996. ISBN: 978-3-642-05220-0.
[60] Jack K. Hale. *Ordinary Dierential Equations*. 2nd ed. Pure and Applied Mathematics 21. Malabar, Fla., USA: Robert E. Krieger Publishing Company,
1980.
[61] Michael Hinze, René Pinnau, Michael Ulbrich, and Stefan Ulbrich. *Optimiza-* *tion with PDE Constraints*. New York, Berlin: Springer, 2009. ISBN: 978-1- 402-08838-4.
[62] Christoph Huck. “Perturbation Analysis and Numerical Discretisation of Hy- perbolic Partial Dierential Algebraic Equations Describing Flow Networks.” Doctoral Thesis. 2018. DOI: 10.18452/19596.
[63] Gunay Ismayilova. “The Problem of the Optimal Control with a Lower Co- ecient for Weakly Nonlinear Wave Equation in the Mixed Problem.” In: *European Journal of Pure and Applied Mathematics* 13.2 (2020), pp. 314–
322. DOI: 10.29020/nybg.ejpam.v13i2.3650.
[64] Lennart Jansen. “A Dissection Concept for DAEs. Structural Decoupling, Unique Solvability, Convergence Theory and Half-Explicit Methods.” PhD thesis. Humboldt-Universität zu Berlin, 2014.
[65] Lennart Jansen, Michael Matthes, and Caren Tischendorf. “Global Unique Solvability for Memristive Circuit DAEs of Index 1.” In: *International Journal* *of Circuit Theory and Applications* 43.1 (2015), pp. 73–93. DOI: 10. 1002 /cta.1927.
[66] Konrad Jörgens. “Das Anfangswertproblem im Großen für eine Klasse nicht- linearer Wellengleichungen.” German. In: *Mathematische Zeitschrift* 77 (1961), pp. 295–308. DOI: 10.1007/bf01180181.
[67] Tobias Thomas Köppel. “Multi-scale Modeling of Flow and Transport Pro- cesses in Arterial Networks and Tissue.” Doctoral Thesis. 2015.
[68] Miroslav Krstic and Ji Wang. “Cable-Operated Elevators and Deep-Sea Con- struction. 4 × 4 Hyperbolic PDE-ODE Control with Moving Boundary.” In: *Advances in Distributed Parameter Systems*. Ed. by Jean Auriol, Joachim Deutscher, Guilherme Mazanti, and Giorgio Valmorbida. Advances in Delays and Dynamics 14. Cham: Springer International Publishing, 2022, pp. 199–
225. ISBN: 978-3-030-94766-8. DOI: 10.1007/978-3-030-94766-8_9.
<u>Bibliography</u>
[69] Karl Kunisch and Hannes Meinlschmidt. “Optimal Control of an Energy- Critical Semilinear Wave Equation in 3D with Spatially Integrated Control Constraints.” In: *Journal de Mathématiques Pures et Appliquées* 138 (2020), pp. 46–87. ISSN: 0021-7824. DOI: 10.1016/j.matpur.2020.03.006.
[70] Karl Kunisch, Philip Trautmann, and Boris Vexler. “Optimal Control of the Undamped Linear Wave Equation with Measure Valued Controls.” In: *SIAM* *Journal on Control and Optimization* 54.3 (2016), pp. 1212–1244.
[71] Peter Kunkel and Volker Mehrmann. *Dierential-Algebraic Equations. Anal-* *ysis and Numerical Solution*. European Mathematical Society Press, 2006. ISBN: 978-3-037-19017-3. DOI: 10.4171/017.
[72] René Lamour, Roswitha März, and Caren Tischendorf. *Dierential-Algebraic* *Equations: A Projector Based Analysis*. Dierential-Algebraic Equations Fo- rum. Berlin: Springer, 2013. ISBN: 978-3-642-27554-8.
[73] Irena Lasiecka, Jacques-Louis Lions, and Roberto Triggiani. “Non Homoge- neous Boundary Value Problems for Second Order Hyperbolic Operators.” In: *Journal de Mathématiques Pures et Appliquées* 65.2 (1986), pp. 149–192. [74] Irena Lasiecka and Roberto Triggiani. “Recent Advances in Regularity of Second-order Hyperbolic Mixed Problems, and Applications.” In: *Dynamics* *Reported. Expositions in Dynamical Systems*. Ed. by Christopher K. R. T. Jones, Urs Kirchgraber, and Hans-Otto Walther. Berlin, Heidelberg: Springer, 1994, pp. 104–162. ISBN: 978-3-642-78234-3. DOI: 10.1007/978-3-642-7823 4-3_3.
[75] Irena Lasiecka and Roberto Triggiani. “Regularity Theory of Hyperbolic Equa- tions with Non-homogeneous Neumann Boundary Conditions. II: General Boundary Data.” In: *Journal of Dierential Equations* 94.1 (1991), pp. 112–
164. ISSN: 0022-0396. DOI: 10.1016/0022-0396(91)90106-j.
[76] Irena Lasiecka and Roberto Triggiani. “Sharp Regularity Theory for Second Order Hyperbolic Equations of Neumann Type. I: L₂ Nonhomogeneous Data.” In: *Annali di Matematica pura ed applicata* 157 (1990), pp. 285–367. DOI:
10.1007/bf01765322.
[77] Peter David Lax. *Hyperbolic Systems of Conservation Laws and the Math-* *ematical Theory of Shock Waves*. CBMS-NSF Regional Conference Series in Applied Mathematics 11. Society for Industrial and Applied Mathematics,
1973. ISBN: 978-0-898-71177-6.
[78] Tatsien Li and Yi Zhou. *Nonlinear Wave Equations*. Series in Contemporary Mathematics. Berlin: Springer, 2017. ISBN: 978-3-662-55725-9. DOI: 10.100 7/978-3-662-55725-9.
[79] Thibault Liard, Raphael Stern, and Maria Laura Delle Monache. “A PDE- ODE Model for Trac Control with Autonomous Vehicles.” In: *Networks* *and Heterogeneous Media* 18.3 (2023), pp. 1190–1206. ISSN: 1556-1801. DOI:
10.3934/nhm.2023051.
<u>Bibliography</u>
[80] Joram Lindenstrauss and Lior Tzafriri. “On the Complemented Subspaces Problems.” In: *Israel Journal of Mathematics* 9.2 (1971), pp. 263–269. DOI:
10.1007/bf02771592.
[81] Jacques-Louis Lions. *Optimal Control of Systems Governed by Partial Dif-* *ferential Equations*. Die Grundlagen der mathematischen Wissenschaften in Einzeldarstellungen 170. Berlin: Springer, 1971. ISBN: 978-3-540-05115-2.
[82] Jacques-Louis Lions. *Quelques méthodes de résolution des problèmes aux lim-* *ites non linéaires*. French. Paris: S. A. Dunod, 1969.
[83] Jacques-Louis Lions and Enrico Magenes. *Non-Homogeneous Boundary Value* *Problems and Applications*. Trans. French by P. Kenneth. Vol. 1. Die Grund- lagen der mathematischen Wissenschaften in Einzeldarstellungen 181. Berlin, Heidelberg: Springer, 1972. ISBN: 978-3-642-65163-2. DOI: 10.1007/978-3-6 42-65161-8.
[84] Jacques-Louis Lions and Enrico Magenes. *Non-Homogeneous Boundary Value* *Problems and Applications*. Trans. French by P. Kenneth. Vol. 2. Die Grund- lagen der mathematischen Wissenschaften in Einzeldarstellungen 182. Berlin, Heidelberg: Springer, 1972. ISBN: 978-3-642-65219-6. DOI: 10.1007/978-3-6 42-65217-2.
[85] Roswitha März. “Dierential-Algebraic Equations from a Functional-Analytic Viewpoint: A Survey.” In: *Surveys in Dierential-Algebraic Equations II*. Ed. by Achim Ilchmann and Timo Reis. Dierential-Algebraic Equations Forum. Cham: Springer, 2015, pp. 163–286. ISBN: 978-3-319-11050-9. DOI: 10.1007 /978-3-319-11050-9.
[86] Michael Matthes. “Numerical Analysis of Nonlinear Partial Dierential-Alge- braic Equations. A Coupled and an Abstract Systems Approach.” PhD thesis. Universität zu Köln, 2012. ISBN: 978-3-832-53278-9.
[87] Vuk Milisic and Alo Quarteroni. “Analysis of Lumped Parameter Models for Blood Flow Simulations and their Relation with 1D Models.” In: *Math-* *ematical Modelling and Numerical Analysis* 38 (2004), pp. 613–632. DOI:
10.1051/m2an:2004036.
[88] Jason J. Molitierno. *Applications of Combinatorial Matrix Theory to Lapla-* *cian Matrices of Graphs*. Discrete Mathematics and its Applications. Boca Raton; London; New York: CRC Press, 2012. ISBN: 978-1-439-86337-4.
[89] Mohammed Zuhair Nashed. “Generalized Inverses, Normal Solvability, and Iteration for Singular Operator Equations.” In: *Nonlinear Functional Analysis* *and Applications*. Ed. by Louis B. Rall. Academic Press, 1971, pp. 311–359. ISBN: 978-0-12-576350-9. DOI: 10.1016/b978-0-12-576350-9.50007-2.
[90] Mohammed Zuhair Nashed. “Inner, Outer, and Generalized Inverses in Ba- nach and Hilbert Spaces.” In: *Numerical Functional Analysis and Optimiza-* *tion* 9.3-4 (1987), pp. 261–325. DOI: 10.1080/01630568708816235.
<u>Bibliography</u>
[91] Mohammed Zuhair Nashed and George Frank Votruba. “A Unied Approach to Generalized Inverses of Linear Operators. I. Algebraic, Toplogical and Pro- jectional Properties.” In: *Bulletin of the American Mathematical Society* 80.5 (1974), pp. 825–830.
[92] Mohammed Zuhair Nashed and George Frank Votruba. “A Unied Approach to Generalized Inverses of Linear Operators. II. Extremal and Proximal Prop- erties.” In: *Bulletin of the American Mathematical Society* 80 (1974), pp. 831–
835.
[93] Peter J. Olver. *Introduction to Partial Dierential Equations*. Undergraduate Texts in Mathematics. Springer Cham, 2014. ISBN: 978-3-319-02099-0. DOI:
10.1007/978-3-319-02099-0.
[94] Jonas Pade. “Analysis and Waveform Relaxation for a Dierential-Algebraic Electrical Circuit Model.” PhD thesis. Humboldt-Universität zu Berlin, 2021.
[95] Amnon Pazy. *Semigroups of Linear Operators and Applications to Partial* *Dierential Equations*. Applied Mathematical Sciences 44. New York: Sprin- ger, 1983. ISBN: 978-1-461-25561-1. DOI: 10.1007/978-1-4612-5561-1.
[96] Nicolas Petit and Pierre Rouchon. “Flatness of heavy chain systems.” In: *SIAM Journal on Control and Optimization* 40.2 (2001), pp. 475–495.
[97] Linda Petzold. “Dierential/Algebraic Equations are not ODE’s.” In: *SIAM* *Journal on Scientic and Statistical Computing* 3.3 (1982), pp. 367–384. DOI:
10.1137/0903023.
[98] Sebastian Pfa and Stefan Ulbrich. “Optimal Boundary Control of Nonlin- ear Hyperbolic Conservation Laws with Switched Boundary Data.” In: *SIAM* *Journal on Control and Optimization* 53.3 (2015), pp. 1250–1277. DOI: 10.1 137/140995799.
[99] Nikolay I. Pogodaev. “Bang-Bang Theorem for a Coupled ODE-PDE Control System.” In: *Journal of Mathematical Sciences* 239.2 (2019), pp. 146–158. DOI: 10.1007/s10958-019-04298-7.
[100] Jerey Rauch. *Hyperbolic Partial Dierential Equations and Geometric Op-* *tics*. Graduate Studies in Mathematics 133. Rhode Island: American Mathe- matical Society, 2012. ISBN: 978-0-821-87291-8.
[101] Jean-Pierre Raymond and Hasnaa Zidani. “Hamiltonian Pontryagin’s Princi- ples for Control Problems Governed by Semilinear Parabolic Equations.” In: *Applied Mathematics and Optimization* 39 (1999), pp. 143–177.
[102] Tomáš Roucíček. *Nonlinear Partial Dierential Equations with Applications*. International Series of Numerical Mathematics 153. Basel: Birkhäuser, 2005. ISBN: 978-3-764-37293-4.
[103] Michael Růz̉ic̉ka. *Nichtlineare Funktionalanalysis. Eine Einführung*. German. 2nd ed. Masterclass. Springer, 2020. ISBN: 978-3-662-62190-5.
<u>Bibliography</u>
[104] Sandro Salsa, Federico Mario Giovanni Vegni, Anna Zaretti, and Paolo Zunino. *A Primer on PDEs. Models, Methods, Simulations*. UNITEXT – La Matem- atica per il 3+2 65. Milan: Springer, 2013. ISBN: 978-8-847-02861-6. DOI:
10.1007/978-88-470-2862-3.
[105] Leonard Isaac Schi. “Nonlinear Meson Theory of Nuclear Forces. I. Neutral Scalar Mesons with Point-Contact Repulsion.” In: *Physical Review* 84.1 (Oct.
1951), pp. 1–9. DOI: 10.1103/PhysRev.84.1.
[106] Johann Michael Schmitt and Stefan Ulbrich. “Optimal Boundary Control of Hyperbolic Balance Laws with State Constraints.” In: *SIAM Journal on* *Control and Optimization* 59.2 (2021), pp. 1341–1369. DOI: 10.1137/19m12 9797x.
[107] Sebastian Schöps. “Multiscale Modeling and Multirate Time-Integration of Field/Circuit Coupled Problems.” Doctoral Thesis. 2011.
[108] Ben Schweizer. *Partielle Dierentialgleichungen. Eine anwendungsorientierte* *Einführung*. German. 2nd ed. Masterclass. Berlin, Heidelberg: Springer Spek- trum, 2018. ISBN: 978-3-662-56667-1.
[109] Jalal Shatah and Michael Struwe. *Geometric Wave Equations*. Courant Lec- ture Notes in Mathematics 2. New York: American Mathematical Society,
2000. ISBN: 978-0-821-82749-9.
[110] Jalal Shatah and Michael Struwe. “Regularity Results for Nonlinear Wave Equations.” In: *Annals of Mathematics* 138.3 (1993), pp. 503–518. ISSN: 0003486x. DOI: 10.2307/2946554.
[111] Yubing Shi, Patricia Lawford, and Rodney Hose. “Review of Zero-D and 1-D Models of Blood Flow in the Cardiovascular System.” In: *BioMedical Engi-* *neering OnLine* 10.1 (2011), p. 33. DOI: 10.1186/1475-925x-10-33.
[112] Bernd Simeon. *Computational Flexible Multibody Dynamics. A Dierential-* *Algebraic Approach*. Dierential-Algebraic Equations Forum. Berlin, Heidel- berg: Springer, 2013. ISBN: 978-3-642-35157-0. DOI: 10.1007/978-3-642-35 158-7.
[113] Bernd Simeon. “On the History of Dierential-Algebraic Equations. A Retro- spective with Personal Side Trips.” In: *Surveys in Dierential-Algebraic Equa-* *tions IV*. Ed. by Achim Ilchmann and Timo Reis. Dierential-Algebraic Equa- tions Forum. Cham: Springer, 2017, pp. 1–39. ISBN: 978-3-319-46618-7. DOI:
10.1007/978-3-319-46618-7.
[114] Bernd Simeon and Martin Arnold. “Coupling DAEs and PDEs for Simulating the Interaction of Pantograph and Catenary.” In: *Mathematical and Computer* *Modelling of Dynamical Systems* 6.2 (2000), pp. 129–144. DOI: 10.1076/138 7-3954(200006)6:2;1-m;ft129. p [115] Jacques Simon. “Compact Sets in the Space L (0,T; B).” In: *Annali di Matem-* *atica pura ed applicata* 146.1 (1986), pp. 65–96. DOI: 10.1007/bf01762360.
<u>Bibliography</u>
[116] Gerd Steinebach, Roland Rosen, and Annelie Sohr. “Modeling and Numerical Simulation of Pipe Flow Problems in Water Supply Systems.” In: *Mathemati-* *cal Optimization of Water Networks*. Ed. by Alexander Martin et al. Vol. 162. Springer, 2012, pp. 3–15. DOI: 10.1007/978-3-0348-0436-3_1.
[117] Christian Strohm. “Circuit Simulation Including Full-Wave Maxwell’s Equa- tions.” Doctoral Thesis. 2021. DOI: 10.18452/22544.
[118] Roger Temam. *Navier-Stokes Equations and Nonlinear Functional Analysis*. 2nd ed. Society for Industrial and Applied Mathematics, 1995. ISBN: 978-1- 611-97005-0. DOI: 10.1137/1.9781611970050.
[119] Caren Tischendorf. “Coupled Systems of Dierential Algebraic and Partial Dierential Equations in Circuit and Device Simulation. Modeling and Nu- merical Analysis.” Habilitation. Berlin, 2003.
[120] Roberto Triggiani. “Nonlinear Exact Controllability and Nonlinear Stabiliza- tion of Hyperbolic or Hyperbolic-like Evolution Equations.” In: *Matemática* *Contemporânea* 38 (2010). ISSN: 0103-9059,2317-6636. DOI: 10.21711/2317 66362010/rmc381.
[121] Fredi Tröltzsch. *Optimal Control of Partial Dierential Equations. Theory,* *Methods and Applications*. Trans. German by Jürgen Sprekels. Graduate Studies in Mathematics 112. Providence, Rhode Island: American Mathe- matical Society, 2010. ISBN: 978-1-4704-1174-9. DOI: 10.1090/gsm/112.
[122] Fredi Tröltzsch. *Optimale Steuerung partieller Dierentialgleichungen. The-* *orie, Verfahren und Anwendungen*. German. 2nd ed. Wiesbaden: Vieweg + Teubner, 2009. ISBN: 978-3-834-80885-1. DOI: 10.1007/978-3-8348-9357-4.
[123] David Wallauch. “Strichartz Estimates and Blowup Stability for Energy Criti- cal Nonlinear Wave Equations.” In: *Transactions of the American Mathemat-* *ical Society* 376.6 (2023), pp. 4321–4360. ISSN: 1088-6850. DOI: 10. 1090 /tran/8879.
[124] Dirk Werner. *Funktionalanalysis*. German. 7th ed. Berlin: Springer, 2011. ISBN: 978-3-642-21016-7.
[125] Eberhard Zeidler. *Nonlinear Functional Analysis and its Applications*. Vol. I: *Fixed-Point Theorems*. New York: Springer, 1986. ISBN: 978-0-387-90914-1.
[126] Eberhard Zeidler. *Nonlinear Functional Analysis and its Applications*. Vol. II/A: *Linear Monotone Operators*. New York: Springer, 1990. ISBN: 978-1- 461-26971-7.
[127] Eberhard Zeidler. *Nonlinear Functional Analysis and its Applications*. Vol. II/B: *Nonlinear Monotone Operators*. New York: Springer, 1990. ISBN: 978- 1-461-26969-4.
[128] Christoph Zimmer. “Temporal Discretization of Constrained Partial Dier- ential Equations.” PhD thesis. Technische Universität Berlin, 2020.
<u>Bibliography</u>
[129] Enrique Zuazua. “Controllability and Observability of Partial Dierential Equations. Some Results and Open Problems.” In: *Handbook of Dierential* *Equations. Evolutionary Equations*. Ed. by Constantine Michael Dafermos and Eduard Feireisl. Vol. 3. North-Holland, 2007, pp. 527–621. DOI: 10.101 6/s1874-5717(07)80010-7.
[130] Enrique Zuazua. “Exact Controllability for Semilinear Wave Equations in One Space Dimension.” In: *Annales de l’Institut Henri Poincaré C, Analyse non* *linéaire* 10.1 (1993), pp. 109–129.
||Coupled systems of differential-algebraic equations (DAEs) and partial differential equations (PDEs) appear in various fields of applications such as electrical engineering, bio-mathematics, or multi-physics. They are of particular interest for the modeling and simulation of flow networks, for||
|instance energy transport networks.|in which an abstract DAE and a second order hyperbolic PDE are coupled through nonlinear coupling functions. The analysis presented is split into two parts: In the first part, we introduce the concept of matrix-induced linear operators which arise naturally in|In this thesis, we discuss a system|
|literature on abstract DAEs so far.|the context of abstract DAEs but have surprisingly not been discussed in criterion that allows to separate dynamical and non-dynamical parts of the abstract DAE while allowing for a considerable reduction of required assumptions, compared to existing theoretical results for abstract DAEs. In the second part, we build upon the developed techniques. how to combine the theoretical frameworks for abstract DAEs and second order hyperbolic PDEs in a way such that both parts of the solution are of similar regularity. We then use a fixed-point approach to prove existence and uniqueness of local as well as global solutions to the coupled system. In the last part of this thesis, we throw a glance at a related optimal control problem and prove existence of a global minimizer.|We also present a novel index-1-like We show Logos Verlag Berlin ISBN 978-3-8325-5773-7 https://www.logos-verlag.de/oekobuch|