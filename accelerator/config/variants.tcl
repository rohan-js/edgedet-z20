# Supported folding candidates. Each tuple is: name profile PE SIMD.
# Resource/timing selection is made only from post-route reports.
set EDZ_VARIANTS {
    {accuracy_pe4_simd8  accuracy 4 8}
    {accuracy_pe8_simd8  accuracy 8 8}
    {accuracy_pe8_simd16 accuracy 8 16}
    {eco_pe4_simd8       eco      4 8}
    {eco_pe8_simd8       eco      8 8}
    {eco_pe8_simd16      eco      8 16}
}
