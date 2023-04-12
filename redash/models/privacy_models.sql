
--
-- Name: policy_tag; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.policy_tag (
    policy_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: policy_tag policy_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policy_tag
    ADD CONSTRAINT policy_tag_pkey PRIMARY KEY (policy_name);

--
-- Name: query_id_policy_tag_mapping; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.query_id_policy_tag_mapping (
    query_hash character varying(100) NOT NULL,
    policy_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: query_id_policy_tag_mapping query_id_policy_tag_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.query_id_policy_tag_mapping
    ADD CONSTRAINT query_id_policy_tag_mapping_pkey PRIMARY KEY (query_hash, policy_name);


--
-- Name: ix_query_id_policy_tag_mapping_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_query_id_policy_tag_mapping_created_at ON public.query_id_policy_tag_mapping USING btree (created_at);


--
-- Name: table_column_policy_tag_mapping; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.table_column_policy_tag_mapping (
    project_id character varying(50) NOT NULL,
    dataset_id character varying(50) NOT NULL,
    table_name character varying(100) NOT NULL,
    policy_tag character varying(50) NOT NULL,
    column_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: table_column_policy_tag_mapping table_column_policy_tag_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.table_column_policy_tag_mapping
    ADD CONSTRAINT table_column_policy_tag_mapping_pkey PRIMARY KEY (project_id, dataset_id, table_name, column_name);



--
-- Name: user_group_member_list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_group_member_list (
    user_emails character varying[] NOT NULL,
    policy_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_group_member_list user_group_member_list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_group_member_list
    ADD CONSTRAINT user_group_member_list_pkey PRIMARY KEY (policy_name);
