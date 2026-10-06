// Untested draft copied verbatim from docs/VEGAS_NOTES.md Section 10. Do not run on real projects.
using System;
using System.IO;
using System.Text;
using System.Windows.Forms;
using ScriptPortal.Vegas;

public class EntryPoint
{
    static string Esc(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", " ").Replace("\n", " ");
    }

    public void FromVegas(Vegas vegas)
    {
        try
        {
            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "VegasAgent\\probes");
            Directory.CreateDirectory(dir);

            StringBuilder sb = new StringBuilder();
            sb.Append("{\r\n");
            sb.Append("  \"project_path\": \"").Append(Esc(vegas.Project.FilePath)).Append("\",\r\n");
            // FrameRate is a double; the true rational rate must be inferred (VQ-11).
            sb.Append("  \"fps_double\": ").Append(vegas.Project.Video.FrameRate.ToString("R")).Append(",\r\n");
            sb.Append("  \"tracks\": [\r\n");

            int ti = 0;
            foreach (Track track in vegas.Project.Tracks)
            {
                sb.Append("    {\"index\":").Append(ti)
                  .Append(",\"kind\":\"").Append(track.IsVideo() ? "video" : "audio").Append("\"")
                  .Append(",\"name\":\"").Append(Esc(track.Name)).Append("\"")
                  .Append(",\"events\":[\r\n");

                int ei = 0;
                foreach (TrackEvent ev in track.Events)
                {
                    string media = "";
                    double offsetMs = 0;
                    try
                    {
                        if (ev.ActiveTake != null)
                        {
                            media = ev.ActiveTake.MediaPath;
                            offsetMs = ev.ActiveTake.Offset.ToMilliseconds();
                        }
                    }
                    catch { }

                    bool grouped = false;
                    try { grouped = (ev.Group != null); } catch { }

                    sb.Append("      {\"i\":").Append(ei)
                      .Append(",\"start_ms\":").Append(ev.Start.ToMilliseconds().ToString("R"))
                      .Append(",\"length_ms\":").Append(ev.Length.ToMilliseconds().ToString("R"))
                      .Append(",\"take_offset_ms\":").Append(offsetMs.ToString("R"))
                      .Append(",\"grouped\":").Append(grouped ? "true" : "false")
                      .Append(",\"media\":\"").Append(Esc(media)).Append("\"},\r\n");
                    ei++;
                }
                sb.Append("      {}\r\n    ]},\r\n");
                ti++;
            }
            sb.Append("    {}\r\n  ]\r\n}\r\n");

            string path = Path.Combine(dir, "timeline_dump.json");
            File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
            MessageBox.Show("Wrote " + path);
        }
        catch (Exception e)
        {
            MessageBox.Show("TimelineDump failed: " + e.ToString());
        }
    }
}
