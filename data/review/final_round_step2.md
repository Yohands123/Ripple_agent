# Company identity verification

550 source names map to 349 current companies: 201 name variants are combined, including 52 identities beyond prior normalization. Historical company IDs fall from 401 to 350 (51 fewer), with dated pre-merger Mitsumi/Minebea separation.

No duplicate company/event rows or ticker/event stock labels were present to remove: there are 1,655 company/event feature rows and 960 valid supplier stock labels. Every company’s sites share one ID and one ticker within each event. The approved Unimicron correction prevents an unrelated-company merge.

These identity mappings are already active in event-study labels, model features and site projections; step 7 will rerun them with the new supply topology. Counts and checks are recorded in `final_round_step2.json`.
