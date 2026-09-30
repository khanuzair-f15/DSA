class Solution {
public:
    int reverse(int x) {
        long long temp = 0;
        while (x != 0) {

            int digit = x % 10;

            if (temp >  INT_MAX / 10 || temp <  INT_MIN / 10) {
                return 0;
            }

            temp = 1LL * temp * 10 + digit;
            x = x / 10;
        }

        return temp;
    }
};