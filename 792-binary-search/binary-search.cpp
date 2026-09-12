class Solution {
public:
    int search(vector<int>& nums, int key) {

        int low = 0;
        int high = nums.size() - 1;

        while (high >= low) {
            int mid = low + (high - low) / 2;
            if (nums[mid] == key) {
                return mid;
            } else if (nums[mid] > key) {
                high = mid - 1;
            } else {
                low = mid + 1;
            }
        }
        return -1;
    }
};