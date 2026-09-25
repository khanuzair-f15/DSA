// The API isBadVersion is defined for you.
// bool isBadVersion(int version);

class Solution {
public:
    int firstBadVersion(int n) {
        /*
        for (int i = 0; i <= n; i++) {
            if (isBadVersion(i)) {
                cout << isBadVersion(i);
                return i;
            }
        }
        */

        if (isBadVersion(1))
            return 1;
        else {
            int low = 2, high = n, mid;
            while (low <= high) {
                mid = low + (high - low) / 2;
                if (isBadVersion(mid) && isBadVersion(mid - 1) == false)
                    return mid;
                else if (isBadVersion(mid) && isBadVersion(mid - 1) == true)
                    high = mid - 1;
                else
                    low = mid + 1;
            }
            return mid;
        }
    }
};