import requests

from nfl import models

def run():
    login_url = 'https://login.thesolver.com/u/login'
    auth_url = 'https://thesolver.com/api/auth/me'
    projections_url = 'https://api.thesolver.com/api/projections/1001'
    login_payload = {
        'username': 'kkeeling@gmail.com',
        'password': 'hiXEoVzZgA2L.AgMdE3E',
        'state': 'hKFo2SBvN2lDQ2tUOHAwM1RtY2VTMGFsbDZ5bGdmRXd2ZnhqcqFur3VuaXZlcnNhbC1sb2dpbqN0aWTZIHJyN3JXUUNqWEZzYm45M3VoNjQzQlhEeUdMSDk2c2I5o2NpZNkgdHNRdFdzNzVFZVE5S092S2FkOHZzYXZYZmdKeTF3cXc'
    }

    with requests.Session() as s:
        # r = s.post(login_url, login_payload)
        # print(r.status_code)
        # print(s.cookies)
        headers = {
            'Cookie': 'the_solver.0=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwiaWF0IjoxNjY1MTYxNjg1LCJ1YXQiOjE2NjUxNjYxMTIsImV4cCI6MTY2NTI1MjUxMn0..BA9TqRRs-JkQWchk.LRrrmmjA8MrRSsRhpAV-e7wikvdamT8BjGlqV1vzOfTAiNMOWCQQFLn6c2XMecdbIaaKj65fR41n168ZItwzzFGZ3cRFMRrc6GLGKIbfoQ9pN_9Qlwik2f4xobGIvrxhz3g98vu55mKdGH3xUiMb1XyMk88PWzhYqpcAR8dyIfPE-xae0-whfuug5Lsx8urOh2bPQ5_vboD6j1yvEfANXLAOdfptlDRKNJELziWyu-3GBl0VuXQlG8hCobE44D1asixRIaEeGOe_cXWuKpuYD23SglYX2wq8vaeZlTjwbivWseUNmQF0chxkB6airMBeyS712UhZktNbLC-VkxzowKX9u3q7BElhNAcbGVwk2eDfMJqPT6jkgve3A9lKGrYYBphLIPIQ9OGlaNrRKsvgT9heHBvOVcdrOkx0hXK7Vv7tLdaqXgcT2_6_gZWT2w1M5Lyab2zcKhXsJvREwZwwBE0Yam5wWl8TgxfSWrAVEom4FsPmgjJIvideKHJIvABIB9_BEiOgxT2M9yksBV5rRfNBrehEhBmBx_0sPtG5I-sWvsrJOfIAxbF5clr736bTa6jb7MX3P4iEp0QrZWXez1J8Lu8apv9XOZMgz7wTxTvaES90IDsRhEHclRJUPEe3tHEWQ5DtBy1jOsvCrVhCU6p-nXdX7BTt7NIitKubgYe8WaRBKWKDz548_l6co1DeQg9IzemBA4JdnLahezKAisq5Fil2aGr8jyo_pppEBS_YjOn2OneKF2wIFHqgXe6V52ND3HabUvsCJaqa4i_PHxnHZCf7Qf_ToJlEW6c4phT7j2uhhXLx0c5kb4zG0e0JcNgOjQuVRIdPgBmasJZHOZySIho6U38QIFGEzP0ZQQl12Zu5tcmaNVdj3LJjFUUzwtyY6b99J6ncAXQ8sJd82wEWuRikA998fQrxl-YUnDdTRxWhxEkWmSJkTqLLAbxdEAQi__aTA3jVWnuqi_YhVP5VFG8kKwWd9Z28EAzImFTtFHkt4sf3z9QUVnSXKb40ZH72qNDXD9eNkxGHv-EGv6jDnbW5ZgudlqKnp3_W9ZLQCwWO4RrTph2VFkokNd5W5nnjjGFWb065GAZPKd45Up5c1g_Tgc6t5oCWWTlTi52raGTM2yRndkoEqOU4FuJufGKvsjNpmy2JAt3HMGiJzZw8mJFPZ-O4aDSkBL5xnASOHIVjqSENdOAwlaqZrlW9BsOYv8l97HG-GatEZhJdrVj3EYSLOjMhxB1VYBLcEHg_V-os-Qv85QI10FtyJtbea9-t-11f9Y0Vfh9FV7CZ0eh8JSmuDqjfW88q9sOjShbcJDqZN2orwzS-Wya6juQ14XM_zStMm4isef4du_aU9-T_Vsb29qnaOJdV7p0V4vlC4JMjwLclptI1K6Bl4lwCS37UxoWnAHOORI6lnqSK1Dr-dyR3T8P1wPmz-qJgrcStG__uO6RyADpg78Lo-a4IdsnxNOzUjviYAZhUIytK7JloMQIEd1DDWIq9JfW3FJycRWVzk57Xzk3ZRVJFuhAi1O9amTGxD6sddf1LOleak7ywSCIJdDjgEuF8gQRPWp0f2GxTQggpDjxyrURR7WzcVUU9D-MiSk6WzfZkJCpOoSJnZf3xbmUJlddLo8iSKgIhu_whQhIZmGKtn9cYgmnQ3eQJ4MJykZgAnouZ8cuMR-TsE-E4pdEe61iDQgzpvgkAq9DJ0lfackC14JPPXuhCpCk_HlLjR8kEySaAXJDzMUV8XPSD0serqpnJSfQRXXzxx-JxJr2xZ1Zcj1sZGe3c2IK320rWY26vbXYUnAsWOoG-yoNEf_Z12FRbrTyy8tDFYAE2OmOtvjpovKl4vuET4poGHSUX0wiZCl4AhThlJqgh2tnUZr_cVNTo_FDsZtXvMUS5BAoll6tPOZiWwg6SrS7xvwX7aN-bVeRo3NBY_f5pJSuT9t0PX1GPc-MtGgVJSC_CwxJ-sOnIcXKYsK63NxNkfPrRq68xXz7VatCsztQ8cHzBWtNNP1mOd7SOGHGWkKBw528NjDAyDcHx234_jB4BoS-zDWyTbPjLdUIv9Yta0WSRwMtoZU25Qvvfo4VLUjNxygTyoXsf2KYjMw-7sKBdvZ0baeuTrK74mRu_4uH8IOMG4NTHBE2VAMAQQUGOHZLEhsfnbQ3inIzivOjKdsGmDF1LkxBcBnsFIkiasDWidSqntxv4cwOxfdMPFO0TEx5I5UoH8uxjPn79K3HSX8oISiliYRH3PqZ3khhNK1QZr9S-Jjf6jIvtIupEo7_ix6_mOY8px9xe7olu6aZKyauAZ1mjKiaz3ytOC9etkHND9mG2iT3-IZumzoV-Y9U8WWGY8DvEaFjbT-z5zq2bj9G3jr8Dc5XSmCFz4_qQhRBjM0K1TeTrAhsfccmR6zy63Lfo7qfRH2OiaSMoyCc1M2DtzP7TcLpnWbF-M-SBHcvNNP7MpV8hC_71UlVVV4kwqm5bnWZeFUt2iXP48-Kaxfj5bEX8Puv9u-QILDt8kvEekGApHR4Mm0jySfrfPdDxoX53VITp-Hq6vgVOlGdkIVivAYBgR52bCqtBm-bbxTc8Yj6n6rNBlaFV6nBMxdndgqRh70kj-2YL7FpbpPnBfHsG5ZF3zFCdWXRzG3k3cO3_0LRpWPUb1v6khgMeeivkS3EeFTRPuOpzIXG6BrMVlFvG2c3kzwKGMT7YmLbkVse3-sxK9WZZ5dvsWEwv73fXXyTI3C_v3cJfqsnGwxnc6ess9HAsxm4w52CASitkMtdqQ39UWYqwWYfskZr-hhV8h5IftbIGcAkztb6IITDPiWV0a1Lvm9cp6BdzKfBr9zh_aBm96t7-koTBUxWxd26ZL93GE_KNXsuGt8MgNqW6KWYWsszfNIM40YdzPFgTz4MzCULB45k3FdqvaYN959aAG6YrebQzCpQzGoQPhriVsisMmOOyPL9w7DTKfxcf9Q4d1RGx5rKPybV3phXw-FR8yemD9BumRnYU1gKLOzv_PcCeTC9ZVzJHJUvkkMU-aAfn9tFGJrYjIZPg7Duv7s7-LPun3n-VZFzzoFFFSYTkUrRioJc4H047u_bKPiPF68CvUq4Lom9Sq3ueL01YsylhPbKPkfd8Amoo2ikXXtgJtALqFXuA9wjWHFoXddC3phBJXzio09O1DdLeVnG3KvES-IkypR_NnTec9XdQYgkmdW21QeTIKFc6SW5QXvUqS0r8b_LpjxxmQVQelZjgxA-50XsN6xZ0hMpFJd00011D67lIKqKP97RFLmS56zATWq6puUg4N2un1N4lRjM0ZwzjWZzudFBP_gGvzW1q7WeIgIop9mTeNMjWnL_xUZw-v3Ql3erQWhH6woNOaE_uvQmF47H4eeJacTPG-SStixqsZjohBMUD_UHZeNiDUqsrHKd_ohVK5cuoiu_8xTv3r_0XHwGjvqnZR1giGduU7WpwBOklVV_8a4qWILTPFCzirCLitR3WHjLsBVmXCnVgGWUzLZKhJrHBFiJ7Y_Ca7TA2Ui5DMkalaiNxx-24qvN65SnznkOKqpHyad4mq-7RHIEDh86QLkeC6WnlZ1wQSQz0iv8w6pmlRRamPUeu-IfXE293KA-mbIzZvAz5GziHQJ1nHU6keILc4D7qOPmv3cuciMjD8HWqR3UpFVS2A3Lo5HhevtoL1NLze_aIuJc_6QTeRyui62RgigNoGzQ12L26cAgrp4jP1Hq7oMhQUvHWELMlegb8jD5qNkwlY3vZxLMCBOP9Myca6hktl6tStp1Z0bCIRRU5DHFa-T3cnQ7i0I71sjiwsTi3KUpYEYDoKXBi5zHYsq-B_OL2dEaxJXhZYrACgjBse_Qt7EH; the_solver.1=8Kh5qTvGaYAbxjBCLHc0d0DOS_eve36bB_-eyoDQG4q6Upcdlc829DUwX38fidtZkGt7imdnyIXv-gQfXWYMyegEum2Wj6KAYKbi9tPTZkwqUp5o5SMqRACFMtsuED02BZB1QFUm2Vau_xwCre0GK2WLDY7IKSJX-akniaUof2neOqzL-rzqwQ9ROmkh4rLNLwtcAvtySDYUtUr1CZAAHOme_OPP0E7a-Q6rtLbIw4yoa56cWDJiG87j8U0vMTD0g34ElYGSOMoXkLlFNzYeuvh1crdhuLeFeF2ngngr8sIgaLp7GlQ_VyhpND4kP4odZM3SG8QL1dvuOtyBT6aEqeLTbA9uthS7IUci-wemFka_oMJK-fc1SWeObQ0KUSM3gWD8p0VtYpeO6_QEpO5HpFEaNC5iAK1w0xibRvgmIf0UxnR0i5xg6eBuVVvFpNGr7TK_4zkXSe7IQZjX9tNzybMHBh1yxPebhw-mR1hp_-iVRjq_Fcn0tar0YWyppm8RVl0jdkg_BsKyiz6qXXhdyvm9GzWQCrt6jvnIGMk77P2qtxu55qHBRngMLpY6PIvQ6NlAwDHDCy1uP9fDqkhtV5dTgOJt-TkisKLJxk08T1og8PZCiHFCAvOTvtqAj3CrevkFfwa3fihkK7FL4WQeJqwpVzRajwDTUkJEr9v8TLwjYUVOeNw5FOZaXmb3cJuv-jw.Xns_r_9LZ6Lj8MTV-ZAcPw'
        }
        r2 = s.get(auth_url, headers=headers)
        print(r2.json())

        headers = {
            'Authorization': f'Bearer {r2.json().get("token")}'
        }
        req = requests.Request('GET', projections_url, headers=headers)
        prepped = s.prepare_request(req)
        prepped.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36',
        })
        resp = s.send(prepped)
        # print(resp.text)
        # print(prepped.headers)
        print(resp.status_code)     