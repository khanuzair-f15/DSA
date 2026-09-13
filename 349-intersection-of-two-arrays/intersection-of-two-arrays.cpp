class Solution {
public:
    vector<int> intersection(vector<int>& nums1, vector<int>& nums2) {
        set<int> result; // used to store the common element
        // sort the vector so i can do the set intersection
        sort(nums1.begin(), nums1.end());
        sort(nums2.begin(), nums2.end());

        set_intersection(nums1.begin(), nums1.end(), // first sortered vector
                         nums2.begin(), nums2.end(), // second sortered vector
                         inserter(result, result.begin())); //

        vector<int> ans(result.begin(), result.end());
        return ans;
    }
};