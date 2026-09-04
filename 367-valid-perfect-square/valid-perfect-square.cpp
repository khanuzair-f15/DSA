class Solution {
public:
    bool isPerfectSquare(int num) {

        int low = 0;
        int high = num;

        /*

        5






        */

        while (low <= high) {
            long int mid = low + (high - low) / 2;
            if (num == 1LL * mid * mid) {
                return true;
            } else if (1LL * mid * mid < num) {
                low = mid + 1;
            } else if (1LL * mid * mid > num) {
                high = mid - 1;
            }
        }
        return false;
    }
};