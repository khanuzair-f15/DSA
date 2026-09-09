class Solution {
public:
    bool isThree(int n) {

        int div = 0;

        for (int i = 1; i <= n; i++) {
            if (n % i == 0) {
                div++;
            } else if (div > 3) {
                return false;
            }
        }
        if (div == 3) {
            return true;
        }
        return false;
    }
};