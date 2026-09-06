class Solution {
public:
    int reverseNumber(int x) {
        int temp = x;

        long long num = 0;
        // 25
        while (temp > 0) {
            int digit = temp % 10;
            num = 1LL * num * 10 + digit;
            temp = temp / 10;
        }
        return (int)num;
    }
    int mirrorDistance(int n) { return abs(reverseNumber(n) - n); }
};