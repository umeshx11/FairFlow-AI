#include <cmath>
#include <cstdint>

namespace {
constexpr double kEpsilon = 1e-9;

inline double safe_div(double numerator, double denominator) {
    return denominator <= kEpsilon ? 0.0 : numerator / denominator;
}
}  // namespace

extern "C" {
int ethos_run(const float* y_true,
              const float* y_pred,
              const int32_t* protected_attr,
              const float* proxy_feature,
              const int32_t count,
              float* out_metrics) {
    if (!y_true || !y_pred || !protected_attr || !proxy_feature || !out_metrics || count <= 0) {
        return -1;
    }

    double priv_total = 0.0;
    double unpriv_total = 0.0;
    double priv_selected = 0.0;
    double unpriv_selected = 0.0;

    double priv_true_pos = 0.0;
    double unpriv_true_pos = 0.0;
    double priv_true_neg = 0.0;
    double unpriv_true_neg = 0.0;
    double priv_tp = 0.0;
    double unpriv_tp = 0.0;
    double priv_fp = 0.0;
    double unpriv_fp = 0.0;
    double global_positive = 0.0;

    double sum_x = 0.0;
    double sum_x2 = 0.0;
    double sum_a = 0.0;
    double sum_a2 = 0.0;
    double sum_xa = 0.0;

    for (int32_t i = 0; i < count; ++i) {
        const double y = y_true[i] >= 0.5f ? 1.0 : 0.0;
        const double p = y_pred[i] >= 0.5f ? 1.0 : 0.0;
        const double a = protected_attr[i] > 0 ? 1.0 : 0.0;
        const double x = static_cast<double>(proxy_feature[i]);

        global_positive += p;

        if (a > 0.5) {
            priv_total += 1.0;
            priv_selected += p;
            if (y > 0.5) {
                priv_true_pos += 1.0;
                priv_tp += p;
            } else {
                priv_true_neg += 1.0;
                priv_fp += p;
            }
        } else {
            unpriv_total += 1.0;
            unpriv_selected += p;
            if (y > 0.5) {
                unpriv_true_pos += 1.0;
                unpriv_tp += p;
            } else {
                unpriv_true_neg += 1.0;
                unpriv_fp += p;
            }
        }

        sum_x += x;
        sum_x2 += x * x;
        sum_a += a;
        sum_a2 += a * a;
        sum_xa += x * a;
    }

    const double selection_priv = safe_div(priv_selected, priv_total);
    const double selection_unpriv = safe_div(unpriv_selected, unpriv_total);
    const double disparate_impact = safe_div(selection_unpriv, selection_priv);

    const double tpr_priv = safe_div(priv_tp, priv_true_pos);
    const double tpr_unpriv = safe_div(unpriv_tp, unpriv_true_pos);
    const double fpr_priv = safe_div(priv_fp, priv_true_neg);
    const double fpr_unpriv = safe_div(unpriv_fp, unpriv_true_neg);

    const double tpr_gap = tpr_unpriv - tpr_priv;
    const double fpr_gap = fpr_unpriv - fpr_priv;
    const double equalized_odds_abs = 0.5 * (std::abs(tpr_gap) + std::abs(fpr_gap));

    const double n = static_cast<double>(count);
    const double correlation_num = n * sum_xa - sum_x * sum_a;
    const double correlation_den =
        std::sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_a2 - sum_a * sum_a));
    const double proxy_score =
        correlation_den <= kEpsilon ? 0.0 : std::abs(correlation_num / correlation_den);

    double fairness_checks = 0.0;
    fairness_checks += disparate_impact > 0.8 ? 1.0 : 0.0;
    fairness_checks += std::abs(tpr_gap) < 0.1 ? 1.0 : 0.0;
    fairness_checks += std::abs(fpr_gap) < 0.1 ? 1.0 : 0.0;
    const double fairness_score = (fairness_checks / 3.0) * 100.0;

    out_metrics[0] = static_cast<float>(disparate_impact);
    out_metrics[1] = static_cast<float>(equalized_odds_abs);
    out_metrics[2] = static_cast<float>(tpr_gap);
    out_metrics[3] = static_cast<float>(fpr_gap);
    out_metrics[4] = static_cast<float>(proxy_score);
    out_metrics[5] = static_cast<float>(selection_priv);
    out_metrics[6] = static_cast<float>(selection_unpriv);
    out_metrics[7] = static_cast<float>(safe_div(global_positive, n));
    out_metrics[8] = static_cast<float>(fairness_score);
    out_metrics[9] = static_cast<float>(n);

    return 0;
}
}
