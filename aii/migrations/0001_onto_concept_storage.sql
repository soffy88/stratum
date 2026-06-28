-- AII 概念存储层 + _onto 六表 + 统一本性表 schema 快照 (migration / 重建用)
-- 守 VHDX 数据丢失教训: DDL 固化进 repo, 不依赖现库存活.
-- 来源: pg_dump --schema-only -t 'aii.*_onto' -t aii.invariant (已应用态快照)
-- 含: ku_onto/edge_onto/concept_onto(本体列+invariant_id)/ku_concept_onto/kc_onto/bu_onto/invariant
--   invariant=统一本性表(单本性 is_concept=false + 本性概念 is_concept=true 同表, 一对多member).
-- 前置依赖: pgvector. 重建前需 CREATE EXTENSION IF NOT EXISTS vector;

--
-- PostgreSQL database dump
--

\restrict bnFIvOLaI3If2FaEsaZlsQaIFbe6YyXXWlb9bzqAPOQFlaRDrCLGwHJmhmB02y8

-- Dumped from database version 16.14 (Ubuntu 16.14-1.pgdg22.04+1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-1.pgdg22.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bu_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.bu_onto (
    bu_id bigint NOT NULL,
    substrate_id text NOT NULL,
    doc_type text,
    source_credibility text,
    problem_statement text,
    overview_oneline text,
    learning_thread text,
    applicability jsonb,
    core_takeaways jsonb,
    main_claims jsonb,
    argument_structure jsonb,
    core_explanations jsonb,
    concept_network jsonb,
    structure jsonb,
    key_concept_ku_ids jsonb,
    positional_summary jsonb,
    grade text DEFAULT 'unverified'::text,
    synthesis_marker text DEFAULT 'AII综合,非原文断言'::text NOT NULL,
    member_kc_ids jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bu_onto_grade_check CHECK ((grade = ANY (ARRAY['contradicted'::text, 'high'::text, 'low'::text, 'moderate'::text, 'pending'::text, 'refuted'::text, 'unverified'::text, 'verified'::text])))
);


ALTER TABLE aii.bu_onto OWNER TO aii;

--
-- Name: bu_onto_bu_id_seq; Type: SEQUENCE; Schema: aii; Owner: aii
--

CREATE SEQUENCE aii.bu_onto_bu_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE aii.bu_onto_bu_id_seq OWNER TO aii;

--
-- Name: bu_onto_bu_id_seq; Type: SEQUENCE OWNED BY; Schema: aii; Owner: aii
--

ALTER SEQUENCE aii.bu_onto_bu_id_seq OWNED BY aii.bu_onto.bu_id;


--
-- Name: concept_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.concept_onto (
    concept_id bigint NOT NULL,
    name text NOT NULL,
    name_zh text,
    aliases jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    level text,
    discipline text,
    vector public.vector(1024),
    invariant_id uuid,
    CONSTRAINT concept_onto_level_check CHECK (((level IS NULL) OR (level = ANY (ARRAY['concrete'::text, 'abstract'::text]))))
);


ALTER TABLE aii.concept_onto OWNER TO aii;

--
-- Name: concept_onto_concept_id_seq; Type: SEQUENCE; Schema: aii; Owner: aii
--

CREATE SEQUENCE aii.concept_onto_concept_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE aii.concept_onto_concept_id_seq OWNER TO aii;

--
-- Name: concept_onto_concept_id_seq; Type: SEQUENCE OWNED BY; Schema: aii; Owner: aii
--

ALTER SEQUENCE aii.concept_onto_concept_id_seq OWNED BY aii.concept_onto.concept_id;


--
-- Name: edge_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.edge_onto (
    edge_id bigint NOT NULL,
    substrate_id text NOT NULL,
    src_id text NOT NULL,
    dst_id text NOT NULL,
    relation_type text NOT NULL,
    grade text DEFAULT 'unverified'::text,
    extraction_method text,
    evidence text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT edge_onto_grade_check CHECK ((grade = ANY (ARRAY['contradicted'::text, 'high'::text, 'low'::text, 'moderate'::text, 'pending'::text, 'refuted'::text, 'unverified'::text, 'verified'::text]))),
    CONSTRAINT edge_onto_relation_type_check CHECK ((relation_type = ANY (ARRAY['causes'::text, 'contradicts'::text, 'contrasts_with'::text, 'explains'::text, 'opposes'::text, 'prerequisite_of'::text, 'same_as'::text, 'special_case_of'::text, 'subsumes'::text, 'supported_by'::text])))
);


ALTER TABLE aii.edge_onto OWNER TO aii;

--
-- Name: edge_onto_edge_id_seq; Type: SEQUENCE; Schema: aii; Owner: aii
--

CREATE SEQUENCE aii.edge_onto_edge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE aii.edge_onto_edge_id_seq OWNER TO aii;

--
-- Name: edge_onto_edge_id_seq; Type: SEQUENCE OWNED BY; Schema: aii; Owner: aii
--

ALTER SEQUENCE aii.edge_onto_edge_id_seq OWNED BY aii.edge_onto.edge_id;


--
-- Name: invariant; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.invariant (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    statement text NOT NULL,
    vector public.vector(1024),
    member_concept_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_concept boolean DEFAULT false
);


ALTER TABLE aii.invariant OWNER TO aii;

--
-- Name: kc_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.kc_onto (
    kc_id bigint NOT NULL,
    substrate_id text NOT NULL,
    level integer,
    community_label text,
    summary text,
    member_ku_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    core_concept_id bigint,
    grade text DEFAULT 'unverified'::text,
    synthesis_marker text DEFAULT 'AII综合,非原文断言'::text NOT NULL,
    parent_kc_id bigint,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT kc_onto_grade_check CHECK ((grade = ANY (ARRAY['contradicted'::text, 'high'::text, 'low'::text, 'moderate'::text, 'pending'::text, 'refuted'::text, 'unverified'::text, 'verified'::text])))
);


ALTER TABLE aii.kc_onto OWNER TO aii;

--
-- Name: kc_onto_kc_id_seq; Type: SEQUENCE; Schema: aii; Owner: aii
--

CREATE SEQUENCE aii.kc_onto_kc_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE aii.kc_onto_kc_id_seq OWNER TO aii;

--
-- Name: kc_onto_kc_id_seq; Type: SEQUENCE OWNED BY; Schema: aii; Owner: aii
--

ALTER SEQUENCE aii.kc_onto_kc_id_seq OWNED BY aii.kc_onto.kc_id;


--
-- Name: ku_concept_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.ku_concept_onto (
    ku_id text NOT NULL,
    concept_id bigint NOT NULL
);


ALTER TABLE aii.ku_concept_onto OWNER TO aii;

--
-- Name: ku_onto; Type: TABLE; Schema: aii; Owner: aii
--

CREATE TABLE aii.ku_onto (
    ku_id text NOT NULL,
    substrate_id text NOT NULL,
    title text,
    natural_text text NOT NULL,
    natural_text_zh text,
    knowledge_type text NOT NULL,
    sub_type text,
    is_positional boolean GENERATED ALWAYS AS ((knowledge_type = 'positional'::text)) STORED,
    stance_holder text,
    opposing_stance text,
    grade text DEFAULT 'unverified'::text NOT NULL,
    grounded_by jsonb,
    intuition text,
    insight text,
    example text,
    embedding public.vector(1024),
    valid_from timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    valid_until timestamp with time zone,
    superseded_by text,
    sources jsonb DEFAULT '[]'::jsonb,
    merge_count integer DEFAULT 1,
    provenance jsonb,
    fingerprint text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_ku_onto_grade_mandate CHECK (((grade <> 'verified'::text) OR (COALESCE((grounded_by ->> 'method'::text), 'default'::text) <> 'default'::text))),
    CONSTRAINT ck_ku_onto_positional_holder CHECK (((knowledge_type <> 'positional'::text) OR ((stance_holder IS NOT NULL) AND (stance_holder <> ''::text)))),
    CONSTRAINT ku_onto_grade_check CHECK ((grade = ANY (ARRAY['contradicted'::text, 'high'::text, 'low'::text, 'moderate'::text, 'pending'::text, 'refuted'::text, 'unverified'::text, 'verified'::text]))),
    CONSTRAINT ku_onto_knowledge_type_check CHECK ((knowledge_type = ANY (ARRAY['conceptual'::text, 'rationale'::text, 'factual'::text, 'metacognitive'::text, 'positional'::text, 'procedural'::text]))),
    CONSTRAINT ku_onto_sub_type_check CHECK (((sub_type IS NULL) OR (sub_type = ANY (ARRAY['classification'::text, 'conditional'::text, 'principle'::text, 'self_knowledge'::text, 'skill'::text, 'strategic'::text, 'task_knowledge'::text, 'technique'::text, 'theory'::text]))))
);


ALTER TABLE aii.ku_onto OWNER TO aii;

--
-- Name: bu_onto bu_id; Type: DEFAULT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.bu_onto ALTER COLUMN bu_id SET DEFAULT nextval('aii.bu_onto_bu_id_seq'::regclass);


--
-- Name: concept_onto concept_id; Type: DEFAULT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.concept_onto ALTER COLUMN concept_id SET DEFAULT nextval('aii.concept_onto_concept_id_seq'::regclass);


--
-- Name: edge_onto edge_id; Type: DEFAULT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.edge_onto ALTER COLUMN edge_id SET DEFAULT nextval('aii.edge_onto_edge_id_seq'::regclass);


--
-- Name: kc_onto kc_id; Type: DEFAULT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.kc_onto ALTER COLUMN kc_id SET DEFAULT nextval('aii.kc_onto_kc_id_seq'::regclass);


--
-- Name: bu_onto bu_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.bu_onto
    ADD CONSTRAINT bu_onto_pkey PRIMARY KEY (bu_id);


--
-- Name: bu_onto bu_onto_substrate_id_key; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.bu_onto
    ADD CONSTRAINT bu_onto_substrate_id_key UNIQUE (substrate_id);


--
-- Name: concept_onto concept_onto_name_key; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.concept_onto
    ADD CONSTRAINT concept_onto_name_key UNIQUE (name);


--
-- Name: concept_onto concept_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.concept_onto
    ADD CONSTRAINT concept_onto_pkey PRIMARY KEY (concept_id);


--
-- Name: edge_onto edge_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.edge_onto
    ADD CONSTRAINT edge_onto_pkey PRIMARY KEY (edge_id);


--
-- Name: invariant invariant_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.invariant
    ADD CONSTRAINT invariant_pkey PRIMARY KEY (id);


--
-- Name: kc_onto kc_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.kc_onto
    ADD CONSTRAINT kc_onto_pkey PRIMARY KEY (kc_id);


--
-- Name: ku_concept_onto ku_concept_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.ku_concept_onto
    ADD CONSTRAINT ku_concept_onto_pkey PRIMARY KEY (ku_id, concept_id);


--
-- Name: ku_onto ku_onto_pkey; Type: CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.ku_onto
    ADD CONSTRAINT ku_onto_pkey PRIMARY KEY (ku_id);


--
-- Name: idx_edge_onto_rel; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_edge_onto_rel ON aii.edge_onto USING btree (relation_type);


--
-- Name: idx_edge_onto_src; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_edge_onto_src ON aii.edge_onto USING btree (src_id);


--
-- Name: idx_edge_onto_substrate; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_edge_onto_substrate ON aii.edge_onto USING btree (substrate_id);


--
-- Name: idx_kc_onto_substrate; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_kc_onto_substrate ON aii.kc_onto USING btree (substrate_id);


--
-- Name: idx_ku_onto_embedding; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_ku_onto_embedding ON aii.ku_onto USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_ku_onto_substrate; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_ku_onto_substrate ON aii.ku_onto USING btree (substrate_id);


--
-- Name: idx_ku_onto_type; Type: INDEX; Schema: aii; Owner: aii
--

CREATE INDEX idx_ku_onto_type ON aii.ku_onto USING btree (knowledge_type);


--
-- Name: concept_onto concept_onto_invariant_id_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.concept_onto
    ADD CONSTRAINT concept_onto_invariant_id_fkey FOREIGN KEY (invariant_id) REFERENCES aii.invariant(id);


--
-- Name: kc_onto kc_onto_core_concept_id_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.kc_onto
    ADD CONSTRAINT kc_onto_core_concept_id_fkey FOREIGN KEY (core_concept_id) REFERENCES aii.concept_onto(concept_id);


--
-- Name: kc_onto kc_onto_parent_kc_id_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.kc_onto
    ADD CONSTRAINT kc_onto_parent_kc_id_fkey FOREIGN KEY (parent_kc_id) REFERENCES aii.kc_onto(kc_id);


--
-- Name: ku_concept_onto ku_concept_onto_concept_id_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.ku_concept_onto
    ADD CONSTRAINT ku_concept_onto_concept_id_fkey FOREIGN KEY (concept_id) REFERENCES aii.concept_onto(concept_id) ON DELETE CASCADE;


--
-- Name: ku_concept_onto ku_concept_onto_ku_id_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.ku_concept_onto
    ADD CONSTRAINT ku_concept_onto_ku_id_fkey FOREIGN KEY (ku_id) REFERENCES aii.ku_onto(ku_id) ON DELETE CASCADE;


--
-- Name: ku_onto ku_onto_superseded_by_fkey; Type: FK CONSTRAINT; Schema: aii; Owner: aii
--

ALTER TABLE ONLY aii.ku_onto
    ADD CONSTRAINT ku_onto_superseded_by_fkey FOREIGN KEY (superseded_by) REFERENCES aii.ku_onto(ku_id);


--
-- PostgreSQL database dump complete
--

\unrestrict bnFIvOLaI3If2FaEsaZlsQaIFbe6YyXXWlb9bzqAPOQFlaRDrCLGwHJmhmB02y8

