"""Two manually fitted, model-conditioned appearance-review cameras.

This module does not modify calibration.json, existing cameras,
scene framing, active camera, or timeline markers. Call after the final metric
layout. These are NOT SfM-registered or measurement-accurate cameras. Reference
12 has substantial independent hold-out error from approximate desktop props.

Fit: manual static furniture/rigid-prop correspondences, fixed shared SfM focal
677.778580 px at 1707 x 1280, principal point (853.5, 640). Weighted robust SciPy
least_squares; held-out observations were never used for fitting. Native object
landmarks and observations are embedded for audit; no reference pixels, personal
screen content, or rejected feature matches are included.

Detailed diagnostic evidence: .local/missing-camera-manual-v4 (private).
"""

from __future__ import annotations

import json

SOURCE_NATIVE_SHA256 = "90589108d275c9edaf7518bb1dd0d0e6a731fded89d874cbbec6bfe09eae3c9e"
CANDIDATE_VERSION = "manual_reference_cameras_v4_1"
CAMERA_FITS = json.loads(r"""[
  {
    "reference": 12,
    "focal_mode": "fixed shared SfM focal",
    "focal_px": 677.77858,
    "principal_point_px": [
      853.5,
      640.0
    ],
    "position_world": [
      0.9905701784619506,
      1.9762041813011526,
      1.1819845850567612
    ],
    "rotation_world_to_cv": [
      [
        -0.08972338833067853,
        -0.9959638645907077,
        -0.002386213738324705
      ],
      [
        -0.7658227110469155,
        0.07052204859865494,
        -0.639173071950158
      ],
      [
        0.6367615635630146,
        -0.05552135707087552,
        -0.7690592240379108
      ]
    ],
    "photo_size": [
      1707,
      1280
    ],
    "fit": {
      "count": 6,
      "rmse_euclidean_px": 20.336857652985938,
      "median_px": 18.50289759797015,
      "max_px": 31.121824053121845
    },
    "held_out": {
      "count": 6,
      "rmse_euclidean_px": 64.63759609494448,
      "median_px": 56.838206675975826,
      "max_px": 103.74467116437972
    },
    "correspondences": [
      {
        "id": "D1",
        "pixel_xy": [
          25,
          1064
        ],
        "world_xyz": [
          1.091500163078308,
          2.432500123977661,
          0.7410000562667847
        ],
        "source_object": "Desk_top",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Visible front-left laminate corner beside the wardrobe; includes a few pixels of bevel ambiguity.",
        "predicted_pixel_xy": [
          24.45287419131523,
          1064.4210531515164
        ],
        "residual_xy": [
          -0.5471258086847683,
          0.42105315151638933
        ],
        "error_px": 0.6903856943266172,
        "camera_depth_m": 0.37807738437531174
      },
      {
        "id": "D2",
        "pixel_xy": [
          409,
          447
        ],
        "world_xyz": [
          1.7365001440048218,
          2.432500123977661,
          0.7409999966621399
        ],
        "source_object": "Desk_top",
        "source_feature": "unmodified native bounding corner 1",
        "fit_role": "fit",
        "pixel_pick_sigma": 7,
        "basis": "Visible rear-left laminate corner above the cable, before laptop; manually identified not inferred through occlusion.",
        "predicted_pixel_xy": [
          406.39912057640913,
          418.9920964056113
        ],
        "residual_xy": [
          -2.600879423590868,
          -28.007903594388722
        ],
        "error_px": 28.12840623868745,
        "camera_depth_m": 0.788788626567695
      },
      {
        "id": "S1",
        "pixel_xy": [
          367,
          166
        ],
        "world_xyz": [
          1.596862554550171,
          2.2660531997680664,
          1.0170212984085083
        ],
        "source_object": "Laptop screen lid",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "fit",
        "pixel_pick_sigma": 10,
        "basis": "Outer screen frame upper-left; static rigid prop, but its authored pose/dimensions have model error.",
        "predicted_pixel_xy": [
          386.01516343863983,
          178.31634118466957
        ],
        "residual_xy": [
          19.01516343863983,
          12.316341184669568
        ],
        "error_px": 22.65543424380501,
        "camera_depth_m": 0.4968374077477749
      },
      {
        "id": "S2",
        "pixel_xy": [
          898,
          174
        ],
        "world_xyz": [
          1.596862554550171,
          1.8943381309509277,
          1.0170212984085083
        ],
        "source_object": "Laptop screen lid",
        "source_feature": "unmodified native bounding corner 1",
        "fit_role": "fit",
        "pixel_pick_sigma": 10,
        "basis": "Outer screen frame upper-right; no screen content used.",
        "predicted_pixel_xy": [
          889.5590790215884,
          162.3946687900439
        ],
        "residual_xy": [
          -8.440920978411555,
          -11.605331209956091
        ],
        "error_px": 14.350360952135288,
        "camera_depth_m": 0.5174755328121964
      },
      {
        "id": "S3",
        "pixel_xy": [
          499,
          459
        ],
        "world_xyz": [
          1.5415245294570923,
          2.2660531997680664,
          0.7773262858390808
        ],
        "source_object": "Laptop screen lid",
        "source_feature": "unmodified native bounding corner 3",
        "fit_role": "fit",
        "pixel_pick_sigma": 10,
        "basis": "Outer screen frame lower-left at hinge area; modelled bezel/hinge may differ.",
        "predicted_pixel_xy": [
          499.73484840551146,
          490.1131472245157
        ],
        "residual_xy": [
          0.7348484055114568,
          31.11314722451573
        ],
        "error_px": 31.121824053121845,
        "camera_depth_m": 0.645939940737418
      },
      {
        "id": "S4",
        "pixel_xy": [
          886,
          469
        ],
        "world_xyz": [
          1.5415245294570923,
          1.8943381309509277,
          0.7773262858390808
        ],
        "source_object": "Laptop screen lid",
        "source_feature": "unmodified native bounding corner 0",
        "fit_role": "fit",
        "pixel_pick_sigma": 10,
        "basis": "Outer screen frame lower-right at hinge area.",
        "predicted_pixel_xy": [
          887.1233752382533,
          468.0992554746333
        ],
        "residual_xy": [
          1.1233752382532884,
          -0.9007445253666901
        ],
        "error_px": 1.4399002138685502,
        "camera_depth_m": 0.6665780658018394
      },
      {
        "id": "H1",
        "pixel_xy": [
          450,
          700
        ],
        "world_xyz": [
          1.2620000839233398,
          2.2660531997680664,
          0.7689999938011169
        ],
        "source_object": "Laptop aluminium lower shell",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "held_out",
        "pixel_pick_sigma": 8,
        "basis": "Independent held-out front-left top corner of the laptop base, rounded corner virtual intersection.",
        "predicted_pixel_xy": [
          407.6316266717852,
          749.3672113693666
        ],
        "residual_xy": [
          -42.36837332821477,
          49.3672113693666
        ],
        "error_px": 65.05536578074633,
        "camera_depth_m": 0.4743529294390907
      },
      {
        "id": "H2",
        "pixel_xy": [
          877,
          713
        ],
        "world_xyz": [
          1.2620000839233398,
          1.8943381309509277,
          0.7689999938011169
        ],
        "source_object": "Laptop aluminium lower shell",
        "source_feature": "unmodified native bounding corner 1",
        "fit_role": "held_out",
        "pixel_pick_sigma": 8,
        "basis": "Independent held-out front-right top corner of the laptop base.",
        "predicted_pixel_xy": [
          933.1472503831712,
          708.9129546701749
        ],
        "residual_xy": [
          56.14725038317124,
          -4.0870453298250595
        ],
        "error_px": 56.29580504014991,
        "camera_depth_m": 0.4949910545035121
      },
      {
        "id": "H3",
        "pixel_xy": [
          508,
          772
        ],
        "world_xyz": [
          1.2620000839233398,
          2.2024831771850586,
          0.765500009059906
        ],
        "source_object": "Tablet dark glass border",
        "source_feature": "unmodified native bounding corner 6",
        "fit_role": "held_out",
        "pixel_pick_sigma": 10,
        "basis": "Held-out tablet glass far-left virtual corner; a separate rigid prop not in fit.",
        "predicted_pixel_xy": [
          502.7095502156539,
          744.7837777698212
        ],
        "residual_xy": [
          -5.2904497843460945,
          -27.2162222301788
        ],
        "error_px": 27.725648980739233,
        "camera_depth_m": 0.48057411891114565
      },
      {
        "id": "H4",
        "pixel_xy": [
          824,
          777
        ],
        "world_xyz": [
          1.2620000839233398,
          1.9831420183181763,
          0.765500009059906
        ],
        "source_object": "Tablet dark glass border",
        "source_feature": "unmodified native bounding corner 5",
        "fit_role": "held_out",
        "pixel_pick_sigma": 10,
        "basis": "Held-out tablet glass far-right virtual corner.",
        "predicted_pixel_xy": [
          811.8642618278146,
          720.9173995855348
        ],
        "residual_xy": [
          -12.13573817218537,
          -56.08260041446522
        ],
        "error_px": 57.380608311801744,
        "camera_depth_m": 0.49275223771293347
      },
      {
        "id": "H5",
        "pixel_xy": [
          405,
          1037
        ],
        "world_xyz": [
          1.1019999980926514,
          2.2024831771850586,
          0.765500009059906
        ],
        "source_object": "Tablet dark glass border",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "held_out",
        "pixel_pick_sigma": 10,
        "basis": "Held-out tablet glass near-left virtual corner.",
        "predicted_pixel_xy": [
          434.0279705232395,
          992.2801050730784
        ],
        "residual_xy": [
          29.027970523239503,
          -44.7198949269216
        ],
        "error_px": 53.315026727677534,
        "camera_depth_m": 0.37869221408737996
      },
      {
        "id": "H6",
        "pixel_xy": [
          810,
          1057
        ],
        "world_xyz": [
          1.1019999980926514,
          1.9831420183181763,
          0.765500009059906
        ],
        "source_object": "Tablet dark glass border",
        "source_feature": "unmodified native bounding corner 1",
        "fit_role": "held_out",
        "pixel_pick_sigma": 10,
        "basis": "Held-out tablet glass near-right virtual corner.",
        "predicted_pixel_xy": [
          825.904957582296,
          954.481762016163
        ],
        "residual_xy": [
          15.904957582295992,
          -102.51823798383703
        ],
        "error_px": 103.74467116437972,
        "camera_depth_m": 0.3908703328891678
      }
    ],
    "optimizer_cost": 10.151965329379353,
    "optimizer_success": true,
    "min_depth_m": 0.37807738437531174,
    "jacobian_singular_values": [
      718.7534976133253,
      458.53530305963426,
      176.22992766481764,
      99.42005399115094,
      38.011399363334746,
      11.806786333222714
    ],
    "num_starts": 27,
    "status": "Manual model-conditioned appearance-review camera. Not a survey or SfM registration."
  },
  {
    "reference": 15,
    "focal_mode": "fixed shared SfM focal",
    "focal_px": 677.77858,
    "principal_point_px": [
      853.5,
      640.0
    ],
    "position_world": [
      0.42110003979132143,
      3.7120498789244376,
      1.297811575786976
    ],
    "rotation_world_to_cv": [
      [
        0.3242800625492133,
        -0.9431229560686158,
        -0.07322247448341268
      ],
      [
        -0.336991144456468,
        -0.042848504635667084,
        -0.940532282385037
      ],
      [
        0.8839001129036007,
        0.32967119283747404,
        -0.3317190000921243
      ]
    ],
    "photo_size": [
      1707,
      1280
    ],
    "fit": {
      "count": 8,
      "rmse_euclidean_px": 24.01802137269488,
      "median_px": 13.528685665897516,
      "max_px": 44.157783020772285
    },
    "held_out": {
      "count": 3,
      "rmse_euclidean_px": 14.517881454023188,
      "median_px": 6.238276537061788,
      "max_px": 23.7831681170377
    },
    "correspondences": [
      {
        "id": "U1",
        "pixel_xy": [
          325,
          106
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          1.6200454235076904
        ],
        "source_object": "Bed_end_ladder_rail.007",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Inward-facing rail, far/rear end upper corner at the post joint; bevel makes approximately 3-5 px pick uncertainty.",
        "predicted_pixel_xy": [
          329.6231577597723,
          102.42225920546889
        ],
        "residual_xy": [
          4.623157759772312,
          -3.5777407945311097
        ],
        "error_px": 5.845837567414531,
        "camera_depth_m": 0.6843561667443856
      },
      {
        "id": "U2",
        "pixel_xy": [
          357,
          220
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          1.5560455322265625
        ],
        "source_object": "Bed_end_ladder_rail.007",
        "source_feature": "unmodified native bounding corner 3",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Same inward-facing rail and same rear end, lower corner; not a front/back edge mixture.",
        "predicted_pixel_xy": [
          349.8873331693836,
          176.4188140149186
        ],
        "residual_xy": [
          -7.1126668306163765,
          -43.58118598508139
        ],
        "error_px": 44.157783020772285,
        "camera_depth_m": 0.7055861466861659
      },
      {
        "id": "M1",
        "pixel_xy": [
          437,
          505
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          1.176181674003601
        ],
        "source_object": "Bed_end_ladder_rail.006",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Inward-facing rail, far/rear end upper corner at the post joint; bevel makes approximately 3-5 px pick uncertainty.",
        "predicted_pixel_xy": [
          448.86755098320515,
          537.8544492906501
        ],
        "residual_xy": [
          11.867550983205149,
          32.85444929065011
        ],
        "error_px": 34.93212854280244,
        "camera_depth_m": 0.8315942059070232
      },
      {
        "id": "M2",
        "pixel_xy": [
          459,
          584
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          1.1121817827224731
        ],
        "source_object": "Bed_end_ladder_rail.006",
        "source_feature": "unmodified native bounding corner 3",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Same inward-facing rail and same rear end, lower corner; not a front/back edge mixture.",
        "predicted_pixel_xy": [
          462.6647269568507,
          588.2361434633749
        ],
        "residual_xy": [
          3.6647269568507,
          4.236143463374901
        ],
        "error_px": 5.601351186148044,
        "camera_depth_m": 0.8528241858488036
      },
      {
        "id": "L1",
        "pixel_xy": [
          514,
          777
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          0.8112273216247559
        ],
        "source_object": "Bed_end_ladder_rail.005",
        "source_feature": "unmodified native bounding corner 2",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Inward-facing rail, far/rear end upper corner at the post joint; bevel makes approximately 3-5 px pick uncertainty.",
        "predicted_pixel_xy": [
          519.2999835997829,
          795.0451444522964
        ],
        "residual_xy": [
          5.299983599782877,
          18.045144452296427
        ],
        "error_px": 18.80736729216006,
        "camera_depth_m": 0.9526564987574025
      },
      {
        "id": "L2",
        "pixel_xy": [
          535,
          840
        ],
        "world_xyz": [
          1.0373880863189697,
          4.4597954750061035,
          0.7472273111343384
        ],
        "source_object": "Bed_end_ladder_rail.005",
        "source_feature": "unmodified native bounding corner 3",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Same inward-facing rail and same rear end, lower corner; not a front/back edge mixture.",
        "predicted_pixel_xy": [
          529.8467004650693,
          833.5574794872444
        ],
        "residual_xy": [
          -5.1532995349307384,
          -6.44252051275555
        ],
        "error_px": 8.250004039634975,
        "camera_depth_m": 0.9738865182431693
      },
      {
        "id": "N1",
        "pixel_xy": [
          1322,
          583
        ],
        "world_xyz": [
          1.0450913906097412,
          3.5586185455322266,
          1.1343181133270264
        ],
        "source_object": "Bed_bolt.010",
        "source_feature": "native bolt centre (mean bounding corners)",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Clearly exposed near/front-post bolt beside the shirt, aligned with middle rail; native placement is authored.",
        "predicted_pixel_xy": [
          1291.7918198806435,
          579.0407572636769
        ],
        "residual_xy": [
          -30.208180119356484,
          -3.9592427363230627
        ],
        "error_px": 30.46653490583744,
        "camera_depth_m": 0.5551980226300309
      },
      {
        "id": "N2",
        "pixel_xy": [
          1238,
          929
        ],
        "world_xyz": [
          1.0450913906097412,
          3.5586185455322266,
          0.7693635821342468
        ],
        "source_object": "Bed_bolt.009",
        "source_feature": "native bolt centre (mean bounding corners)",
        "fit_role": "fit",
        "pixel_pick_sigma": 5,
        "basis": "Clearly exposed near/front-post bolt just below the shirt hem, aligned with lower rail.",
        "predicted_pixel_xy": [
          1240.112838733154,
          933.9756386184145
        ],
        "residual_xy": [
          2.1128387331539216,
          4.97563861841445
        ],
        "error_px": 5.405651410641712,
        "camera_depth_m": 0.6762603747963897
      },
      {
        "id": "H1",
        "pixel_xy": [
          307,
          163
        ],
        "world_xyz": [
          1.0182561874389648,
          4.481248378753662,
          1.568318247795105
        ],
        "source_object": "Bed_bolt.015",
        "source_feature": "native bolt centre (mean bounding corners)",
        "fit_role": "held_out",
        "pixel_pick_sigma": 5,
        "basis": "Held-out rear-post bolt at upper rail; independently visible dark circular centre.",
        "predicted_pixel_xy": [
          312.9736662832753,
          161.20238900511941
        ],
        "residual_xy": [
          5.973666283275293,
          -1.7976109948805856
        ],
        "error_px": 6.238276537061788,
        "camera_depth_m": 0.6916767705375425
      },
      {
        "id": "H2",
        "pixel_xy": [
          425,
          552
        ],
        "world_xyz": [
          1.0182561874389648,
          4.481248378753662,
          1.1343181133270264
        ],
        "source_object": "Bed_bolt.014",
        "source_feature": "native bolt centre (mean bounding corners)",
        "fit_role": "held_out",
        "pixel_pick_sigma": 5,
        "basis": "Held-out rear-post bolt at middle rail; independently visible small dark centre.",
        "predicted_pixel_xy": [
          431.87169988015256,
          574.7688125830134
        ],
        "residual_xy": [
          6.871699880152562,
          22.768812583013414
        ],
        "error_px": 23.7831681170377,
        "camera_depth_m": 0.8356428611831411
      },
      {
        "id": "H3",
        "pixel_xy": [
          505,
          821
        ],
        "world_xyz": [
          1.0182561874389648,
          4.481248378753662,
          0.7693635821342468
        ],
        "source_object": "Bed_bolt.013",
        "source_feature": "native bolt centre (mean bounding corners)",
        "fit_role": "held_out",
        "pixel_pick_sigma": 6,
        "basis": "Held-out rear-post bolt at lower rail, to the left of the clip lamp.",
        "predicted_pixel_xy": [
          504.1567718935277,
          826.2000415636351
        ],
        "residual_xy": [
          -0.8432281064722815,
          5.200041563635068
        ],
        "error_px": 5.267966011951583,
        "camera_depth_m": 0.9567052133494999
      }
    ],
    "optimizer_cost": 36.146593633108786,
    "optimizer_success": true,
    "min_depth_m": 0.5551980226300309,
    "jacobian_singular_values": [
      529.5452184873509,
      413.7104178543955,
      232.54530405428642,
      165.1618891926276,
      65.98042214886792,
      31.873498275494793
    ],
    "num_starts": 27,
    "status": "Manual model-conditioned appearance-review camera. Not a survey or SfM registration."
  }
]""")


def add_manual_reference_cameras_v4():
    """Add only missing reference 12/15; return objects keyed by reference number.

    Repeat calls are safe for cameras authored by this module. A pre-existing
    camera with either reserved name from another source raises an error, rather
    than silently overwriting evidence. The other thirteen reference cameras and
    all timeline markers are left untouched. Render callers must explicitly clear
    camera marker bindings in their disposable render scene before rendering.
    """
    import bpy
    from mathutils import Matrix, Vector

    collection_name = "Manual Reference Cameras v4 (approximate)"
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    made = {}
    cv_to_blender = Matrix.Diagonal((1.0, -1.0, -1.0))
    for fit in CAMERA_FITS:
        number = fit["reference"]
        name = f"Camera_Reference_{number:02d}"
        camera = bpy.data.objects.get(name)
        if camera is not None and camera.get("manual_camera_source") != CANDIDATE_VERSION:
            raise ValueError(f"Refusing to replace existing camera from another source: {name}")
        if camera is None:
            data = bpy.data.cameras.new(name)
            camera = bpy.data.objects.new(name, data)
            collection.objects.link(camera)
        data = camera.data
        data.type = "PERSP"
        data.sensor_fit = "HORIZONTAL"
        data.sensor_width = 36.0
        data.lens = fit["focal_px"] * data.sensor_width / fit["photo_size"][0]
        data.shift_x = 0.0
        data.shift_y = 0.0
        data.clip_start = 0.01
        data.clip_end = 100.0
        data.dof.use_dof = False
        matrix = (Matrix(fit["rotation_world_to_cv"]).transposed() @ cv_to_blender).to_4x4()
        matrix.translation = Vector(fit["position_world"])
        camera.matrix_world = matrix
        camera["manual_camera_source"] = CANDIDATE_VERSION
        camera["fit_status"] = (
            "Approximate model-conditioned appearance review; not SfM registration"
        )
        camera["fit_rmse_px"] = fit["fit"]["rmse_euclidean_px"]
        camera["held_out_rmse_px"] = fit["held_out"]["rmse_euclidean_px"]
        camera["held_out_max_px"] = fit["held_out"]["max_px"]
        camera["source_native_sha256"] = SOURCE_NATIVE_SHA256
        camera["fit_observations"] = fit["fit"]["count"]
        camera["held_out_observations"] = fit["held_out"]["count"]
        camera["reference_size"] = "1707 x 1280"
        camera["exposure_ev"] = 0.65
        camera["exposure_status"] = (
            "Provisional shared detail-view exposure; not radiometrically measured"
        )
        made[number] = camera
    return made
