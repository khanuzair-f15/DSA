class Solution {
public:
    bool isUgly(int n) {
        // 6 3 1
        while (n >= 1) {
            int temp = n;

            if (n == 1) {
                return true;
            }
            if (n % 2 == 0) {
                n = n / 2;
            } else if (n % 3 == 0) {
                n = n / 3;
            } else if (n % 5 == 0) {
                n = n / 5;
            }
            if (temp == n) {
                return false;
            }
        }
        return false;
    }
};