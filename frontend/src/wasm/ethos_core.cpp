#include <cmath>
#include <cstdint>
#include <cstring>

namespace {
constexpr double kEpsilon = 1e-9;
constexpr char kHexDigits[] = "0123456789abcdef";
constexpr int32_t kSha256HexLength = 64;
constexpr int32_t kTokenHexPrefix = 20;
constexpr int32_t kPiiTokenLength = 5 + kTokenHexPrefix;

inline double safe_div(double numerator, double denominator) {
    return denominator <= kEpsilon ? 0.0 : numerator / denominator;
}

inline uint32_t rotr(uint32_t value, uint32_t bits) {
    return (value >> bits) | (value << (32 - bits));
}

inline uint32_t choose(uint32_t e, uint32_t f, uint32_t g) {
    return (e & f) ^ (~e & g);
}

inline uint32_t majority(uint32_t a, uint32_t b, uint32_t c) {
    return (a & b) ^ (a & c) ^ (b & c);
}

inline uint32_t sigma0(uint32_t x) {
    return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
}

inline uint32_t sigma1(uint32_t x) {
    return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
}

inline uint32_t gamma0(uint32_t x) {
    return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
}

inline uint32_t gamma1(uint32_t x) {
    return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
}

struct Sha256Ctx {
    uint8_t data[64];
    uint32_t datalen;
    uint64_t bitlen;
    uint32_t state[8];
};

constexpr uint32_t kRoundConstants[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
    0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
    0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
    0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
};

void sha256_transform(Sha256Ctx* ctx, const uint8_t* block) {
    uint32_t message_schedule[64];
    for (uint32_t i = 0, j = 0; i < 16; ++i, j += 4) {
        message_schedule[i] = (static_cast<uint32_t>(block[j]) << 24) |
                              (static_cast<uint32_t>(block[j + 1]) << 16) |
                              (static_cast<uint32_t>(block[j + 2]) << 8) |
                              static_cast<uint32_t>(block[j + 3]);
    }
    for (uint32_t i = 16; i < 64; ++i) {
        message_schedule[i] = gamma1(message_schedule[i - 2]) + message_schedule[i - 7] +
                              gamma0(message_schedule[i - 15]) + message_schedule[i - 16];
    }

    uint32_t a = ctx->state[0];
    uint32_t b = ctx->state[1];
    uint32_t c = ctx->state[2];
    uint32_t d = ctx->state[3];
    uint32_t e = ctx->state[4];
    uint32_t f = ctx->state[5];
    uint32_t g = ctx->state[6];
    uint32_t h = ctx->state[7];

    for (uint32_t i = 0; i < 64; ++i) {
        const uint32_t temp1 = h + sigma1(e) + choose(e, f, g) + kRoundConstants[i] + message_schedule[i];
        const uint32_t temp2 = sigma0(a) + majority(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

void sha256_init(Sha256Ctx* ctx) {
    ctx->datalen = 0;
    ctx->bitlen = 0;
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
}

void sha256_update(Sha256Ctx* ctx, const uint8_t* data, size_t len) {
    for (size_t i = 0; i < len; ++i) {
        ctx->data[ctx->datalen] = data[i];
        ctx->datalen += 1;
        if (ctx->datalen == 64) {
            sha256_transform(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

void sha256_final(Sha256Ctx* ctx, uint8_t hash[32]) {
    uint32_t i = ctx->datalen;
    if (ctx->datalen < 56) {
        ctx->data[i++] = 0x80;
        while (i < 56) {
            ctx->data[i++] = 0x00;
        }
    } else {
        ctx->data[i++] = 0x80;
        while (i < 64) {
            ctx->data[i++] = 0x00;
        }
        sha256_transform(ctx, ctx->data);
        std::memset(ctx->data, 0, 56);
    }

    ctx->bitlen += static_cast<uint64_t>(ctx->datalen) * 8;
    ctx->data[63] = static_cast<uint8_t>(ctx->bitlen);
    ctx->data[62] = static_cast<uint8_t>(ctx->bitlen >> 8);
    ctx->data[61] = static_cast<uint8_t>(ctx->bitlen >> 16);
    ctx->data[60] = static_cast<uint8_t>(ctx->bitlen >> 24);
    ctx->data[59] = static_cast<uint8_t>(ctx->bitlen >> 32);
    ctx->data[58] = static_cast<uint8_t>(ctx->bitlen >> 40);
    ctx->data[57] = static_cast<uint8_t>(ctx->bitlen >> 48);
    ctx->data[56] = static_cast<uint8_t>(ctx->bitlen >> 56);
    sha256_transform(ctx, ctx->data);

    for (i = 0; i < 4; ++i) {
        hash[i] = static_cast<uint8_t>((ctx->state[0] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 4] = static_cast<uint8_t>((ctx->state[1] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 8] = static_cast<uint8_t>((ctx->state[2] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 12] = static_cast<uint8_t>((ctx->state[3] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 16] = static_cast<uint8_t>((ctx->state[4] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 20] = static_cast<uint8_t>((ctx->state[5] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 24] = static_cast<uint8_t>((ctx->state[6] >> (24 - i * 8)) & 0x000000ff);
        hash[i + 28] = static_cast<uint8_t>((ctx->state[7] >> (24 - i * 8)) & 0x000000ff);
    }
}

void write_hex(const uint8_t* bytes, int32_t byte_count, char* out_text) {
    for (int32_t i = 0; i < byte_count; ++i) {
        const uint8_t value = bytes[i];
        out_text[i * 2] = kHexDigits[(value >> 4) & 0x0F];
        out_text[i * 2 + 1] = kHexDigits[value & 0x0F];
    }
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

int ethos_sha256_hex(const uint8_t* input, const int32_t length, char* out_hex, const int32_t out_capacity) {
    if (!input || length < 0 || !out_hex || out_capacity < (kSha256HexLength + 1)) {
        return -1;
    }

    Sha256Ctx ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, input, static_cast<size_t>(length));
    uint8_t digest[32];
    sha256_final(&ctx, digest);
    write_hex(digest, 32, out_hex);
    out_hex[kSha256HexLength] = '\0';
    return 0;
}

int ethos_hash_pii_token(const uint8_t* input,
                         const int32_t length,
                         char* out_token,
                         const int32_t out_capacity) {
    if (!input || length < 0 || !out_token || out_capacity < (kPiiTokenLength + 1)) {
        return -1;
    }

    char full_hash[kSha256HexLength + 1];
    if (ethos_sha256_hex(input, length, full_hash, kSha256HexLength + 1) != 0) {
        return -2;
    }

    out_token[0] = 'h';
    out_token[1] = 'a';
    out_token[2] = 's';
    out_token[3] = 'h';
    out_token[4] = '_';
    for (int32_t i = 0; i < kTokenHexPrefix; ++i) {
        out_token[5 + i] = full_hash[i];
    }
    out_token[kPiiTokenLength] = '\0';
    return 0;
}
}
