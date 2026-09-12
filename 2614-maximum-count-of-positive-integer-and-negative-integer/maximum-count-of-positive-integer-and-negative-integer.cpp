class Solution {
public:
    int maximumCount(vector<int>& nums) {

        int n = nums.size();

        int low = 0;
        int high = n - 1;

        // Find first non-negative number
        while (low <= high) {

            int mid = low + (high - low) / 2;

            if (nums[mid] < 0) {
                low = mid + 1;
            } 
            else {
                high = mid - 1;
            }
        }

        int negative = low;

        // Find first positive number
        low = 0;
        high = n - 1;

        while (low <= high) {

            int mid = low + (high - low) / 2;

            if (nums[mid] <= 0) {
                low = mid + 1;
            } 
            else {
                high = mid - 1;
            }
        }

        int positive = n - low;

        return max(negative, positive);
    }
};