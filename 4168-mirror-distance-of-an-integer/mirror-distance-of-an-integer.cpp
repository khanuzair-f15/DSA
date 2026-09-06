class Solution {
public:
    int reverseNumber(int x) {
        long long num = 0;
        // 8.55
        while (x > 0) {
            int digit = x % 10;
            num = 1LL * num * 10 + digit;
            x = x / 10;
        }
        return (int)num;
    }
    int mirrorDistance(int n) { return abs(reverseNumber(n) - n); }
};