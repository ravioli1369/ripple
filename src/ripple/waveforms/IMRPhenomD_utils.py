from typing import Tuple

import jax.numpy as jnp
import jax

from ..constants import gt
from ..typing import Array
from .IMRPhenomD_QNMdata import QNMData_a, QNMData_fRD, QNMData_fdamp


def EradRational0815_s(eta, s):
    eta2 = eta * eta
    eta3 = eta2 * eta
    eta4 = eta3 * eta

    return (
        (
            0.055974469826360077 * eta
            + 0.5809510763115132 * eta2
            - 0.9606726679372312 * eta3
            + 3.352411249771192 * eta4
        )
        * (
            1.0
            + (
                -0.0030302335878845507
                - 2.0066110851351073 * eta
                + 7.7050567802399215 * eta2
            )
            * s
        )
    ) / (
        1.0
        + (-0.6714403054720589 - 1.4756929437702908 * eta + 7.304676214885011 * eta2)
        * s
    )


def EradRational0815(eta, chi1, chi2):
    Seta = jnp.sqrt(1.0 - 4.0 * eta)
    m1 = 0.5 * (1.0 + Seta)
    m2 = 0.5 * (1.0 - Seta)
    m1s = m1 * m1
    m2s = m2 * m2
    s = (m1s * chi1 + m2s * chi2) / (m1s + m2s)

    return EradRational0815_s(eta, s)


def get_fRD_fdamp(m1, m2, chi1, chi2):
    m1_s = m1 * gt
    m2_s = m2 * gt
    M_s = m1_s + m2_s
    eta_s = m1_s * m2_s / (M_s ** 2.0)
    S = (chi1 * m1_s ** 2 + chi2 * m2_s ** 2) / (M_s ** 2.0)
    eta2 = eta_s * eta_s
    eta3 = eta2 * eta_s
    S2 = S * S
    S3 = S2 * S

    a = eta_s * (
        3.4641016151377544
        - 4.399247300629289 * eta_s
        + 9.397292189321194 * eta2
        - 13.180949901606242 * eta3
        + S
        * (
            (1.0 / eta_s - 0.0850917821418767 - 5.837029316602263 * eta_s)
            + (0.1014665242971878 - 2.0967746996832157 * eta_s) * S
            + (-1.3546806617824356 + 4.108962025369336 * eta_s) * S2
            + (-0.8676969352555539 + 2.064046835273906 * eta_s) * S3
        )
    )

    fRD = jnp.interp(a, QNMData_a, QNMData_fRD) / (
        1.0 - EradRational0815(eta_s, chi1, chi2)
    )
    fdamp = jnp.interp(a, QNMData_a, QNMData_fdamp) / (
        1.0 - EradRational0815(eta_s, chi1, chi2)
    )

    return fRD / M_s, fdamp / M_s


def get_transition_frequencies(
    theta: Array, gamma2: float, gamma3: float
) -> Tuple[float, float, float, float, float, float]:

    m1, m2, chi1, chi2 = theta
    M = m1 + m2
    f_RD, f_damp = get_fRD_fdamp(m1, m2, chi1, chi2)

    # Phase transition frequencies
    f1 = 0.018 / (M * gt)
    f2 = f_RD / 2.0

    # Amplitude transition frequencies
    f3 = 0.014 / (M * gt)
    f4_gammaneg_gtr_1 = lambda f_RD_, f_damp_, gamma3_, gamma2_: jnp.abs(
        f_RD_ + (-f_damp_ * gamma3_) / gamma2_
    )
    f4_gammaneg_less_1 = lambda f_RD_, f_damp_, gamma3_, gamma2_: jnp.abs(
        f_RD_ + (f_damp_ * (-1 + jnp.sqrt(1 - (gamma2_) ** 2.0)) * gamma3_) / gamma2_
    )
    f4 = jax.lax.cond(
        gamma2 >= 1,
        f4_gammaneg_gtr_1,
        f4_gammaneg_less_1,
        f_RD,
        f_damp,
        gamma3,
        gamma2,
    )
    return f1, f2, f3, f4, f_RD, f_damp


@jax.jit
def get_coeffs(theta: Array) -> Array:
    # Retrives the coefficients needed to produce the waveform

    m1, m2, chi1, chi2 = theta
    m1_s = m1 * gt
    m2_s = m2 * gt
    M_s = m1_s + m2_s
    eta = m1_s * m2_s / (M_s ** 2.0)

    # Definition of chiPN from lalsuite
    chi_s = (chi1 + chi2) / 2.0
    chi_a = (chi1 - chi2) / 2.0
    seta = (1 - 4 * eta) ** (1 / 2)
    chiPN = chi_s * (1 - 76 * eta / 113) + seta * chi_a

    coeff = (
        PhenomD_coeff_table[:, 0]
        + PhenomD_coeff_table[:, 1] * eta
        + (chiPN - 1.0)
        * (
            PhenomD_coeff_table[:, 2]
            + PhenomD_coeff_table[:, 3] * eta
            + PhenomD_coeff_table[:, 4] * (eta ** 2.0)
        )
        + (chiPN - 1.0) ** 2.0
        * (
            PhenomD_coeff_table[:, 5]
            + PhenomD_coeff_table[:, 6] * eta
            + PhenomD_coeff_table[:, 7] * (eta ** 2.0)
        )
        + (chiPN - 1.0) ** 3.0
        * (
            PhenomD_coeff_table[:, 8]
            + PhenomD_coeff_table[:, 9] * eta
            + PhenomD_coeff_table[:, 10] * (eta ** 2.0)
        )
    )

    # FIXME: Change to dictionary lookup
    return coeff


def get_delta0(f1, f2, f3, v1, v2, v3, d1, d3):
    return (
        -(d3 * f1 ** 2 * (f1 - f2) ** 2 * f2 * (f1 - f3) * (f2 - f3) * f3)
        + d1 * f1 * (f1 - f2) * f2 * (f1 - f3) * (f2 - f3) ** 2 * f3 ** 2
        + f3 ** 2
        * (
            f2
            * (f2 - f3) ** 2
            * (-4 * f1 ** 2 + 3 * f1 * f2 + 2 * f1 * f3 - f2 * f3)
            * v1
            + f1 ** 2 * (f1 - f3) ** 3 * v2
        )
        + f1 ** 2
        * (f1 - f2) ** 2
        * f2
        * (f1 * f2 - 2 * f1 * f3 - 3 * f2 * f3 + 4 * f3 ** 2)
        * v3
    ) / ((f1 - f2) ** 2 * (f1 - f3) ** 3 * (f2 - f3) ** 2)


def get_delta1(f1, f2, f3, v1, v2, v3, d1, d3):
    return (
        d3 * f1 * (f1 - f3) * (f2 - f3) * (2 * f2 * f3 + f1 * (f2 + f3))
        - (
            f3
            * (
                d1
                * (f1 - f2)
                * (f1 - f3)
                * (f2 - f3) ** 2
                * (2 * f1 * f2 + (f1 + f2) * f3)
                + 2
                * f1
                * (
                    f3 ** 4 * (v1 - v2)
                    + 3 * f2 ** 4 * (v1 - v3)
                    + f1 ** 4 * (v2 - v3)
                    + 4 * f2 ** 3 * f3 * (-v1 + v3)
                    + 2 * f1 ** 3 * f3 * (-v2 + v3)
                    + f1
                    * (
                        2 * f3 ** 3 * (-v1 + v2)
                        + 6 * f2 ** 2 * f3 * (v1 - v3)
                        + 4 * f2 ** 3 * (-v1 + v3)
                    )
                )
            )
        )
        / (f1 - f2) ** 2
    ) / ((f1 - f3) ** 3 * (f2 - f3) ** 2)


def get_delta2(f1, f2, f3, v1, v2, v3, d1, d3):
    return (
        d1
        * (f1 - f2)
        * (f1 - f3)
        * (f2 - f3) ** 2
        * (f1 * f2 + 2 * (f1 + f2) * f3 + f3 ** 2)
        - d3
        * (f1 - f2) ** 2
        * (f1 - f3)
        * (f2 - f3)
        * (f1 ** 2 + f2 * f3 + 2 * f1 * (f2 + f3))
        - 4 * f1 ** 2 * f2 ** 3 * v1
        + 3 * f1 * f2 ** 4 * v1
        - 4 * f1 * f2 ** 3 * f3 * v1
        + 3 * f2 ** 4 * f3 * v1
        + 12 * f1 ** 2 * f2 * f3 ** 2 * v1
        - 4 * f2 ** 3 * f3 ** 2 * v1
        - 8 * f1 ** 2 * f3 ** 3 * v1
        + f1 * f3 ** 4 * v1
        + f3 ** 5 * v1
        + f1 ** 5 * v2
        + f1 ** 4 * f3 * v2
        - 8 * f1 ** 3 * f3 ** 2 * v2
        + 8 * f1 ** 2 * f3 ** 3 * v2
        - f1 * f3 ** 4 * v2
        - f3 ** 5 * v2
        - (f1 - f2) ** 2
        * (
            f1 ** 3
            + f2 * (3 * f2 - 4 * f3) * f3
            + f1 ** 2 * (2 * f2 + f3)
            + f1 * (3 * f2 - 4 * f3) * (f2 + 2 * f3)
        )
        * v3
    ) / ((f1 - f2) ** 2 * (f1 - f3) ** 3 * (f2 - f3) ** 2)


def get_delta3(f1, f2, f3, v1, v2, v3, d1, d3):
    return (
        (d3 * (f1 - f3) * (2 * f1 + f2 + f3)) / (f2 - f3)
        - (d1 * (f1 - f3) * (f1 + f2 + 2 * f3)) / (f1 - f2)
        + (
            2
            * (
                f3 ** 4 * (-v1 + v2)
                + 2 * f1 ** 2 * (f2 - f3) ** 2 * (v1 - v3)
                + 2 * f2 ** 2 * f3 ** 2 * (v1 - v3)
                + 2 * f1 ** 3 * f3 * (v2 - v3)
                + f2 ** 4 * (-v1 + v3)
                + f1 ** 4 * (-v2 + v3)
                + 2
                * f1
                * f3
                * (f3 ** 2 * (v1 - v2) + f2 ** 2 * (v1 - v3) + 2 * f2 * f3 * (-v1 + v3))
            )
        )
        / ((f1 - f2) ** 2 * (f2 - f3) ** 2)
    ) / (f1 - f3) ** 3


def get_delta4(f1, f2, f3, v1, v2, v3, d1, d3):
    return (
        -(d3 * (f1 - f2) ** 2 * (f1 - f3) * (f2 - f3))
        + d1 * (f1 - f2) * (f1 - f3) * (f2 - f3) ** 2
        - 3 * f1 * f2 ** 2 * v1
        + 2 * f2 ** 3 * v1
        + 6 * f1 * f2 * f3 * v1
        - 3 * f2 ** 2 * f3 * v1
        - 3 * f1 * f3 ** 2 * v1
        + f3 ** 3 * v1
        + f1 ** 3 * v2
        - 3 * f1 ** 2 * f3 * v2
        + 3 * f1 * f3 ** 2 * v2
        - f3 ** 3 * v2
        - (f1 - f2) ** 2 * (f1 + 2 * f2 - 3 * f3) * v3
    ) / ((f1 - f2) ** 2 * (f1 - f3) ** 3 * (f2 - f3) ** 2)


PhenomD_coeff_table = jnp.array(
    [
        [  # rho1 (element 0)
            3931.8979897196696,
            -17395.758706812805,
            3132.375545898835,
            343965.86092361377,
            -1.2162565819981997e6,
            -70698.00600428853,
            1.383907177859705e6,
            -3.9662761890979446e6,
            -60017.52423652596,
            803515.1181825735,
            -2.091710365941658e6,
        ],
        [  # rho2 (element 1)
            -40105.47653771657,
            112253.0169706701,
            23561.696065836168,
            -3.476180699403351e6,
            1.137593670849482e7,
            754313.1127166454,
            -1.308476044625268e7,
            3.6444584853928134e7,
            596226.612472288,
            -7.4277901143564405e6,
            1.8928977514040343e7,
        ],
        [  # rho3 (element 2)
            83208.35471266537,
            -191237.7264145924,
            -210916.2454782992,
            8.71797508352568e6,
            -2.6914942420669552e7,
            -1.9889806527362722e6,
            3.0888029960154563e7,
            -8.390870279256162e7,
            -1.4535031953446497e6,
            1.7063528990822166e7,
            -4.2748659731120914e7,
        ],
        [  # v2 (element 3)
            0.8149838730507785,
            2.5747553517454658,
            1.1610198035496786,
            -2.3627771785551537,
            6.771038707057573,
            0.7570782938606834,
            -2.7256896890432474,
            7.1140380397149965,
            0.1766934149293479,
            -0.7978690983168183,
            2.1162391502005153,
        ],
        [  # gamma1 (element 4)
            0.006927402739328343,
            0.03020474290328911,
            0.006308024337706171,
            -0.12074130661131138,
            0.26271598905781324,
            0.0034151773647198794,
            -0.10779338611188374,
            0.27098966966891747,
            0.0007374185938559283,
            -0.02749621038376281,
            0.0733150789135702,
        ],
        [  # gamma2 (element 5)
            1.010344404799477,
            0.0008993122007234548,
            0.283949116804459,
            -4.049752962958005,
            13.207828172665366,
            0.10396278486805426,
            -7.025059158961947,
            24.784892370130475,
            0.03093202475605892,
            -2.6924023896851663,
            9.609374464684983,
        ],
        [  # gamma3 (element 6)
            1.3081615607036106,
            -0.005537729694807678,
            -0.06782917938621007,
            -0.6689834970767117,
            3.403147966134083,
            -0.05296577374411866,
            -0.9923793203111362,
            4.820681208409587,
            -0.006134139870393713,
            -0.38429253308696365,
            1.7561754421985984,
        ],
        [  # sig1 (element 7)
            2096.551999295543,
            1463.7493168261553,
            1312.5493286098522,
            18307.330017082117,
            -43534.1440746107,
            -833.2889543511114,
            32047.31997183187,
            -108609.45037520859,
            452.25136398112204,
            8353.439546391714,
            -44531.3250037322,
        ],
        [  # sig2 (element 8)
            -10114.056472621156,
            -44631.01109458185,
            -6541.308761668722,
            -266959.23419307504,
            686328.3229317984,
            3405.6372187679685,
            -437507.7208209015,
            1.6318171307344697e6,
            -7462.648563007646,
            -114585.25177153319,
            674402.4689098676,
        ],
        [  # sig3 (element 9)
            22933.658273436497,
            230960.00814979506,
            14961.083974183695,
            1.1940181342318142e6,
            -3.1042239693052764e6,
            -3038.166617199259,
            1.8720322849093592e6,
            -7.309145012085539e6,
            42738.22871475411,
            467502.018616601,
            -3.064853498512499e6,
        ],
        [  # sig4 (element 10)
            -14621.71522218357,
            -377812.8579387104,
            -9608.682631509726,
            -1.7108925257214056e6,
            4.332924601416521e6,
            -22366.683262266528,
            -2.5019716386377467e6,
            1.0274495902259542e7,
            -85360.30079034246,
            -570025.3441737515,
            4.396844346849777e6,
        ],
        [  # beta1 (element 11)
            97.89747327985583,
            -42.659730877489224,
            153.48421037904913,
            -1417.0620760768954,
            2752.8614143665027,
            138.7406469558649,
            -1433.6585075135881,
            2857.7418952430758,
            41.025109467376126,
            -423.680737974639,
            850.3594335657173,
        ],
        [  # beta2 (element 12)
            -3.282701958759534,
            -9.051384468245866,
            -12.415449742258042,
            55.4716447709787,
            -106.05109938966335,
            -11.953044553690658,
            76.80704618365418,
            -155.33172948098394,
            -3.4129261592393263,
            25.572377569952536,
            -54.408036707740465,
        ],
        [  # beta3 (element 13)
            -0.000025156429818799565,
            0.000019750256942201327,
            -0.000018370671469295915,
            0.000021886317041311973,
            0.00008250240316860033,
            7.157371250566708e-6,
            -0.000055780000112270685,
            0.00019142082884072178,
            5.447166261464217e-6,
            -0.00003220610095021982,
            0.00007974016714984341,
        ],
        [  # a1 (element 14)
            43.31514709695348,
            638.6332679188081,
            -32.85768747216059,
            2415.8938269370315,
            -5766.875169379177,
            -61.85459307173841,
            2953.967762459948,
            -8986.29057591497,
            -21.571435779762044,
            981.2158224673428,
            -3239.5664895930286,
        ],
        [  # a2 (element 15)
            -0.07020209449091723,
            -0.16269798450687084,
            -0.1872514685185499,
            1.138313650449945,
            -2.8334196304430046,
            -0.17137955686840617,
            1.7197549338119527,
            -4.539717148261272,
            -0.049983437357548705,
            0.6062072055948309,
            -1.682769616644546,
        ],
        [  # a3 (element 16)
            9.5988072383479,
            -397.05438595557433,
            16.202126189517813,
            -1574.8286986717037,
            3600.3410843831093,
            27.092429659075467,
            -1786.482357315139,
            5152.919378666511,
            11.175710130033895,
            -577.7999423177481,
            1808.730762932043,
        ],
        [  # a4 (element 17)
            -0.02989487384493607,
            1.4022106448583738,
            -0.07356049468633846,
            0.8337006542278661,
            0.2240008282397391,
            -0.055202870001177226,
            0.5667186343606578,
            0.7186931973380503,
            -0.015507437354325743,
            0.15750322779277187,
            0.21076815715176228,
        ],
        [  # a5 (element 18)
            0.9974408278363099,
            -0.007884449714907203,
            -0.059046901195591035,
            1.3958712396764088,
            -4.516631601676276,
            -0.05585343136869692,
            1.7516580039343603,
            -5.990208965347804,
            -0.017945336522161195,
            0.5965097794825992,
            -2.0608879367971804,
        ],
    ]
)
