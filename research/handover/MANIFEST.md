# DENT Cursor Handover — File Manifest (research/ tree)

Every transferred file is listed with relative path (from `research/`), size (bytes), known purpose, and SHA-256. Largest file: 9,953,652 bytes (renders) — all are ordinary Git blobs under the 100 MB limit; no Git LFS is used.

Verify after checkout:

```bash
cd research && sha256sum --check handover/MANIFEST.sha256
```

Files listed: 87 (`MANIFEST.md` itself is the only research-tree file without a checksum, since a manifest cannot contain its own hash).

| SHA-256 | Size (B) | Path (from research/) | Purpose |
|---|---|---|---|
| `faa9af14d7621c4d2843f270b31b748a16271864b7f8cf0205c0cda7a4c6d7df` | 41589 | `conserved-material/CONSERVATION_ENGINE_INVESTIGATION.md` | Conserved Material Ledger investigation report |
| `76ca548f5058847653aecc5bd423adf5e8f0fffbbe45a309adb0a34e3f43f031` | 15916 | `conserved-material/cm_rock.py` | Original conserved engine (audit target, unmodified) |
| `494a9c86f11ddbeb15552a6c215a3878c9c159fa9f4eba22c9ccb101c66a5759` | 13246 | `conserved-material/common.py` | Shared geometry/field helpers |
| `c3fe994364dcd39cfa01ba75b5435f0d4d47a55c7a849c8370ed1b80d1f74e5d` | 2394 | `conserved-material/exp1_conservation.py` | E1: material conservation under concentrated/clustered/distributed impact |
| `0af41fb1351ee76f3ee5e215a9d9b735e872501c41ff205bc7319928f2c24124` | 2890 | `conserved-material/exp2_threshold.py` | E2: threshold handling / residual accounting |
| `618281a0314fd57daaee518ba834dfd14182cc9299b3516327dfd6991ca021f0` | 3832 | `conserved-material/exp3_e4_invariant.py` | E3+E4: lifetime invariant bound + spatial differentiation |
| `d8b2bf4c3c066682cfe9f0f4478cf3583e6ff58916dba9a86f7b2c9941e6d3f9` | 10174 | `conserved-material/exp5_surface.py` | E5: surface interaction (craters, bores, floors) |
| `ae4168e90473237410dd429d2d107bf971fb4a9390c7e65bd65225e88101fb9a` | 6067 | `conserved-material/exp6_efficiency.py` | E6: efficiency comparison vs Model A (superseded by Part E re-run) |
| `1a5af5e0bad418caaa0dd89876c10722c1901e040e20c3a57436159df1390b2a` | 3011 | `conserved-material/exp7_terminal.py` | E7: terminal event + idempotency (reduced target) |
| `97dd01b2c2d7345cd7f7b55ce5bba11152edd6c806eeaaa33220ea7361a7dccb` | 1208 | `conserved-material/logs/e5.log` | Raw experiment log |
| `b33c10f470c49417d6ecd8603a031f807cd09d84dceffa935f5faa2636767258` | 12481 | `conserved-material/logs/e5b_fluffquant.log` | Raw experiment log |
| `53242dbc2d7e28c7e6bf081c3b5e7d9f4acbe36ab53928fa6d87871b1045b185` | 386 | `conserved-material/logs/e5c_grazing.log` | Raw experiment log |
| `f357b208cdbee39c2052c9efacae93faaabea366624581289b533f77928edf94` | 1880 | `conserved-material/logs/e6.log` | Raw experiment log |
| `b79fee996263ad1f44f180ddf3beb3e8fa856441a7cb7c2b6a4ad3350ee27de5` | 1012 | `conserved-material/logs/e7.log` | Raw experiment log |
| `ba5e3dd0250cec6bcba58fb92d8875c7d90eda01eac86e46b5ddf0efd1b4c6e9` | 137 | `conserved-material/logs/raycheck1.log` | Raw experiment log |
| `7d21e685acc25871fa0972da86ab827ea91ff168c845feac3e7c6115a38ee366` | 946 | `conserved-material/logs/raycheck2.log` | Raw experiment log |
| `9848a151989ca158f18ee8fcb56bd463af59b98c724d4faea13e065f34e4fbfe` | 30676 | `conserved-material/modelA_stage03.py` | Model A baseline engine (byte-identical copy of stage-0.3 s03_rock.py) |
| `21ba90f0527c5209c116e362fcdef9920ffa504558101530cb9818b3460431be` | 594 | `conserved-material/probe_hash.py` | State hash probing utility |
| `f6e4d84c23204c7b1baa36dfc88948d7a4a14df43e106ed79f1f003ac8e07a03` | 6819 | `conserved-material/results/e1_conservation.json` | Evidence file |
| `20c66b850309f004c5bd7e0f07c1f88e538a7c716652d92905a1ca1e5e38b0da` | 1487 | `conserved-material/results/e2_threshold.json` | Evidence file |
| `2529be394c966eaa059dc098b08800d4f22b5764d662ca86c353d778fd729a1c` | 12468 | `conserved-material/results/e3_e4_invariant.json` | Evidence file |
| `828405eb69f46f9acde2351a9977ad3b17190b48bfa947954048d53f8ecd67b8` | 982 | `conserved-material/results/e5_surface.json` | Evidence file |
| `f8abbc670fd9e16a12eccfa4bca9dd3b195fc0fc063092893d592e04a5462365` | 12480 | `conserved-material/results/e5b_isosurface_agreement.json` | Evidence file |
| `1f0500fba9bbd105f32bc2c2a10279e771529d8633dc636f126ae576a391ca32` | 385 | `conserved-material/results/e5c_grazing_split.json` | Evidence file |
| `4329f9d54b8e84c85aa344143904bd42a630f6c4199c153becf6352083233d4b` | 1840 | `conserved-material/results/e6_efficiency.json` | Evidence file |
| `1be51df3991d86a41e323c0b707143cca2bb424595f91acd01a41e97b89a1db8` | 1011 | `conserved-material/results/e7_terminal.json` | Evidence file |
| `3ed3d152e37c3113d4c439db045364b45e686a3a49f77d0511d34c1c4377950e` | 2115 | `conserved-material/s01_c.py` | Stub voxelizer (originals unavailable; rock recovered from checkpoints) |
| `dcecb300821b78cf3da990eac02330081f191aade7af0be57a4968b1435fbdc4` | 7624 | `conserved-material/streams.py` | Impact stream generators (HistStream, HostileStream, helpers) |
| `17ca57682c5bfdb1758040456f71528526f57bfcee16ff839bc416912530ba4b` | 18970 | `handover/DENT_CURSOR_HANDOVER.md` | Handover document for Cursor (read first) |
| `e6a06215e3e647c093621d3f682d782d627266ee45bd3bb24851bf4f313f6216` | 37170 | `model-a-prime/MODEL_A_PRIME_VALIDATION.md` | Model A' validation report (authoritative) |
| `f56805667904031a6840973fde7c244823351932968b273ae89e52fd6698f7c7` | 32768 | `model-a-prime/db/d10_idempotent.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `f1c24c7eb53960ea06cc3e1f953f467c897cbfbdf9e6d1a18dbfee570c466983` | 32768 | `model-a-prime/db/d11_terminal_restart.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `49b3c37f5ea9dcde691774279e60832d55bfe337f9ddd386b2919ea8c5b1a785` | 32768 | `model-a-prime/db/d1_crash_before.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `61b364deee4fd7915d25b71bf6d6d19fb5f3a0741780f7070afd8ba996e8cf35` | 32768 | `model-a-prime/db/d2_crash_precommit.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `3d772425b3b5b2c84efc63558b2308b2fb24fd0055ced1cde629ff3a35e86ca2` | 32768 | `model-a-prime/db/d3_crash_postcommit.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `28e5aa1bcf4509b189a368d284c7520ec43def56fb822a6e9fffac1802095dda` | 32768 | `model-a-prime/db/d4_crash_terminal.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `32540a29d18d9ff809ce553b9393149e157add4c85ff450a8028d2be3903edde` | 32768 | `model-a-prime/db/d5_crash_before_pub.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `87d5e526651994ee59ad25b37fd8a79fb55b65786491ce65e0a4a321d46aff3a` | 32768 | `model-a-prime/db/d6_crash_during_recovery.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `377ed0719f48db29804decb0dc06f4ad224f7cea2b6b489d582321c0dc374595` | 32768 | `model-a-prime/db/d7_sigkill_mid_txn.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `8e15fe31ec22fac3a31d80340032021d81d57137690934bca42e4a5cf74fa59f` | 32768 | `model-a-prime/db/d8_concurrent_final.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `5b2a302b6cbdb8912701f92c14e11922d8496fde04e38d2cbd9f65f9772b9647` | 32768 | `model-a-prime/db/d9_no_bypass.db` | Synthetic SQLite fixture DB from Part D crash tests (N=10; NOT production data) |
| `d2c7b2b681a15304ab948cf725c7b389339ef5bbd2daba2eff78a0f54c2428ea` | 493 | `model-a-prime/logs/a_adjudicate.log` | Raw experiment log |
| `dc579b44501eefd2d1077ae394f0cdc399ce982faca75c17cfef9953235c0cdb` | 2167 | `model-a-prime/logs/a_adjudicate_all.log` | Raw experiment log |
| `094e1a98a2ae37470ed0f34a7fda85dd38a90b1602d531a54fca5bcb0c20fced` | 1065 | `model-a-prime/logs/a_surface.log` | Raw experiment log |
| `d6a34b19aa0be0e99f58291ff054a69331f6b7e008d0183c2f60fbdd0e93aca0` | 1071 | `model-a-prime/logs/c_geometry.log` | Raw experiment log |
| `70f84489d89002040b07f0ee73afa8a2cb3c29b3669ff5b5fe95dbaa7908d3da` | 9953652 | `model-a-prime/renders/state_C_A_rot.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `0f1e94757d8d07c46a492feb3d078e8c0cc4cc5e5e081ac5fd9b4b1db3ebcfda` | 9948535 | `model-a-prime/renders/state_C_B_distributed.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `87be286b6159744081312eaf872f1510bff15dd9169835435a4b0711b009514d` | 9315184 | `model-a-prime/renders/state_D1_bores.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `ed319aaa9be2124c8e755648a65832731611cd7782d092b64c8cd9fe13822cbf` | 72 | `model-a-prime/renders/state_D1_bores_summary.json` | Damaged-state summary metadata |
| `87be286b6159744081312eaf872f1510bff15dd9169835435a4b0711b009514d` | 9315184 | `model-a-prime/renders/state_D1b_deep_bores.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `ed319aaa9be2124c8e755648a65832731611cd7782d092b64c8cd9fe13822cbf` | 72 | `model-a-prime/renders/state_D1b_deep_bores_summary.json` | Damaged-state summary metadata |
| `cbd20610d479b58df1e293c2d8633492d47d24fd9ab09bf156de1e36665b2f38` | 9504696 | `model-a-prime/renders/state_D2_fragments.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `6a9001c74187be88cc563640b75464bf11c421dc29d079545db0e52528c54d0c` | 72 | `model-a-prime/renders/state_D2_fragments_summary.json` | Damaged-state summary metadata |
| `70f5d14c4cb2b1793444881795c3345dde25248890c9ecf5df535b3252e09ad9` | 8612915 | `model-a-prime/renders/state_D3_hostile.pkl` | Damaged-state checkpoint pickle (input to Part A/C analyses) |
| `ef22fbe090a5da35434bc245799591a065a04cf5fed923d5b7b425f08486276b` | 71 | `model-a-prime/renders/state_D3_hostile_summary.json` | Damaged-state summary metadata |
| `bdd0bb5303c48ad2946846679a36791d469e98c2f491348a488095123d7cd69d` | 2331 | `model-a-prime/results/a_final_stats.json` | Measured: post-adjudication final ray stats (100% within 0.15 cells) |
| `c607a3deca8d1b5f807538cf5b6a3eb4626023d7f933e26637156b13024c3198` | 521 | `model-a-prime/results/a_outlier_adjudication.json` | Measured: 6 outliers adjudicated vs 0.002-cell fine reference |
| `9c33f2ae87ef6443badb86be96d1f581ebe716d14b6d34c4ccf8b0ef72edb3bf` | 8268 | `model-a-prime/results/a_surface.json` | Measured: full ray battery metrics (new vs old vs reference, 3856 rays) |
| `f673d7f2d9cee78fbb7a24cbfcbd2f837248afe4b91dc25ee83875a5ab0e9a09` | 6986 | `model-a-prime/results/b_budget_audit.json` | Measured: 459/6000 over-budget reproduction; 0/6000 corrected; rollback proof |
| `2c273f84a967edda2db40c216386ba9d02a1a3ac94acb1c760f679db5975042a` | 9313 | `model-a-prime/results/c_geometry.json` | Measured: A/B/C/D masses at milestones; adversarial fragment kill |
| `631e07454dbd2af4f1c116d3aab35974977b86ca76271b9eb8ea71cfac3f8d3c` | 1931 | `model-a-prime/results/c_visual_partition.json` | Measured: bond-graph 80k comps vs visual 20 comps (one connected object) |
| `a80adc5d061d78ced93f0d880cd65496e02b1a8ff2719233280002a625acc8b6` | 8634 | `model-a-prime/results/d_durable.json` | Measured: 10/10 durable completion and crash-recovery tests |
| `c07a7d61c5a8ef091c66eb6c7844b9e85a9c6e171adb288621f5d9e7a9130464` | 157 | `model-a-prime/results/det_check.json` | Measured: determinism — two runs identical (hash 354bdb0b...) |
| `940914b61c4f10476acf22ce504aff10942aab7ee87b840d07db78ec93391cc7` | 290 | `model-a-prime/results/e_hier_dda.json` | Measured: hierarchical DDA 0.775x (slower in Python at this scale) |
| `0b623d95102688fe03dc45ea90074ef6ad7808650ea9313809dcf4cf2f8018f7` | 4700 | `model-a-prime/results/e_perf.json` | Measured: E6 root cause + consistent perf re-run (+30/+31% ledger overhead) |
| `0f6255eecbd20e5c23275a13f26751f55f68debb6918b689b0319716e1ee7ff3` | 632 | `model-a-prime/results/f_initial_rock.json` | Measured: exact recovery of 151553 cells / 34,816,588 legacy sum + sha256 |
| `1dda9f33f9a6a115ee62554bda09824741ec2a858474ff44b625e6a1a8bc3c4b` | 416 | `model-a-prime/results/smoke_test.json` | Measured: rock exactness, trilerp equality, 126-ray resolver check |
| `8faeac28f793b4d0e1b7be773e8895526836cfd721eee2e646d1760680262913` | 6232 | `model-a-prime/src/adjudicate_all.py` | Part A: full adjudication -> a_outlier_adjudication.json + a_final_stats.json |
| `d33d6e619e8e6a18f76435df9035e93131db7860ea596baa510bd67562b9a50b` | 5420 | `model-a-prime/src/adjudicate_outliers.py` | Part A: fine 0.002-cell re-reference of err>0.15 rays (subset) |
| `76ca548f5058847653aecc5bd423adf5e8f0fffbbe45a309adb0a34e3f43f031` | 15916 | `model-a-prime/src/cm_rock.py` | Original conserved engine (audit target, unmodified) |
| `494a9c86f11ddbeb15552a6c215a3878c9c159fa9f4eba22c9ccb101c66a5759` | 13246 | `model-a-prime/src/common.py` | Shared geometry/field helpers |
| `9d46d3ef3121e0c79454fa2eeb0fd63dcb2db58efc6b9e3ed473e1411d5a714a` | 16146 | `model-a-prime/src/expA_surface.py` | Part A: 3856-ray surface battery (new/old/independent reference) |
| `a329900f61bbbbc60dcc3e76a988745b3590728828ef668ee5f869db5dab6f55` | 12464 | `model-a-prime/src/expB_budget_audit.py` | Part B: budget defect reproduction + correction + rollback proof |
| `84d9ec90ff925a20e78a905d5ea003c8a8142984392721dfc782eac157fd9e27` | 8139 | `model-a-prime/src/expC_geometry.py` | Part C: A/B/C/D mass milestones + adversarial fragment kill |
| `96dae2a702f75f0d4d91b87cc87f92c907298f74e84c2c3f42742050b3dea2a5` | 12721 | `model-a-prime/src/expD_durable.py` | Part D: 10 crash/idempotency/race tests (writes db/) |
| `cbd2e189a670db8d1144689d3eae35cd58af8b32a6e40f3939f4f0333187d351` | 9878 | `model-a-prime/src/expE_perf.py` | Part E: configuration-matched performance re-run |
| `139b82fd145ba80e464bf8583165be15d901937c6d7632be849c4f9750ef34b2` | 33335 | `model-a-prime/src/maprim_rock.py` | Model A' engine: ledger + ISO ray resolver + transactions |
| `9848a151989ca158f18ee8fcb56bd463af59b98c724d4faea13e065f34e4fbfe` | 30676 | `model-a-prime/src/modelA_stage03.py` | Model A baseline engine (byte-identical copy of stage-0.3 s03_rock.py) |
| `a1ccceb3f60e24cf2bd604b59a7cf0e4329bc12f2f605db35483d31cc264c025` | 2442608 | `model-a-prime/src/pristine_initial.pkl` | Authentic pristine rock: 151553 cells / 34816588 legacy sum |
| `9c6fe608a8b8190096f0c165047aee5ea3496c1d328be593a3810cc44b1f6909` | 3780 | `model-a-prime/src/recover_initial_rock.py` | Part F: reconstructs authentic pristine rock from stage-0.3 checkpoint |
| `3ed3d152e37c3113d4c439db045364b45e686a3a49f77d0511d34c1c4377950e` | 2115 | `model-a-prime/src/s01_c.py` | Stub voxelizer (originals unavailable; rock recovered from checkpoints) |
| `af79945d54103a031a03a548314cc6b885e997e592bbea2250e1bfb184c674a7` | 3895 | `model-a-prime/src/smoke_test.py` | Construction + ref_trilerp equivalence + resolver sanity tests |
| `24a7a40118e53d53cccec94d4a72a8c19095d0e4a21bac5be6e26f3c2daafdd5` | 8199 | `model-a-prime/src/store.py` | SQLite durable completion store (Part D) |
| `dcecb300821b78cf3da990eac02330081f191aade7af0be57a4968b1435fbdc4` | 7624 | `model-a-prime/src/streams.py` | Impact stream generators (HistStream, HostileStream, helpers) |
| `f16ed94da3c0479d2ef5b182e6eae2b0c3ea7ac71a4cd2d8e1b09a0f13fabda3` | 3958 | `model-a-prime/src/supC_visual_partition.py` | Part C supplement: bond graph vs visual 6-connectivity partition |
| `e4e8b2263c113221751c18498fe695fc051b3454664a458b0995659c1d5444c1` | 2244 | `model-a-prime/src/supE_hier_dda.py` | Part E supplement: hierarchical DDA benchmark |
| `83a1a928a6d9caaae552d45eb5ad7335aa49c5ba5e75f280fce8a0c7f31b0a42` | 2854 | `model-a-prime/src/worker.py` | Crash-point tap worker for Part D experiments |
