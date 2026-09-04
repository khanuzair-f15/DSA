class Solution {
public:
    int mySqrt(int x) {
        // 1 2 3 4 5 key = 2
        int high = x;
        int low = 0;
        while (low <= high) {
            int mid = low + (high - low) / 2;
            long long int key = 1LL * mid * mid;
            if (key == x) {
                return mid;
            } else if (x > key) {
                low = mid + 1;
            } else if (x < key) {
                high = mid - 1;
            }
        }
        return high;
    }
};