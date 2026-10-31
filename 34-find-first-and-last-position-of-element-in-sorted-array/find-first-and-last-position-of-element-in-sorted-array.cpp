class Solution {
public:
    vector<int> searchRange(vector<int>& nums, int key) {
        int i = 0;
        int j = nums.size() - 1;
        int l = -1, r = -1;
        while (i <= j) {
            int mid = i + (j - i) / 2;
            if (nums[mid] == key) {
                l = mid;
                j = mid - 1;
            } else if (nums[mid] > key) {
                j = mid - 1;
            } else if (nums[mid] < key) {
                i = mid + 1;
            }
        }
        i = 0;
        j = nums.size() - 1;
        while (i <= j) {
            int mid = i + (j - i + 1) / 2;
            if (nums[mid] == key) {
                r = mid;
                i = mid + 1;
            } else if (nums[mid] > key) {
                j = mid - 1;
            } else if (nums[mid] < key) {
                i = mid + 1;
            }
        }

        return {l, r};
    }
};