class Solution {
public:
    int gcd(int n, int m) {
        if (m != 0) {
            return gcd(m, n % m);
        }
        return n;
    }

    int gcdOfOddEvenSums(int n) { return gcd(n * (n + 1), n * n); }
};